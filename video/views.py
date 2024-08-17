from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import requests
import os
import yt_dlp
import re
from django.conf import settings

# Directory where downloaded videos will be saved
download_path = os.path.join(os.getcwd(), "media")

# Ensure the download path exists
os.makedirs(download_path, exist_ok=True)

def myproject(request):
    return render(request, 'myproject.html')

def extract_video_id(url):
    """
    Extract video ID from various YouTube URL formats.
    """
    match = re.search(r'(?<=v=|embed/|youtu.be/)[\w-]{11}', url)
    if match:
        return match.group(0)
    raise ValueError('Invalid video URL')

def get_video_info(api_key, video_id):
    """
    Fetch video title and duration using YouTube Data API.
    """
    url = f'https://www.googleapis.com/youtube/v3/videos?id={video_id}&key={api_key}&part=contentDetails,snippet'
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError(f'YouTube API request failed with status code {response.status_code}')
    
    data = response.json()
    items = data.get('items', [])
    if items:
        video_info = items[0]
        return {
            'title': video_info['snippet']['title'],
            'duration': video_info['contentDetails']['duration']
        }
    else:
        raise ValueError('Video not found')

@csrf_exempt
def get_video_qualities(request):
    """
    Fetch available video formats and qualities for the given YouTube video URL.
    """
    if request.method == 'POST':
        link = request.POST.get('link')
        api_key = settings.YOUTUBE_API_KEY  # Use environment variable or Django settings
        
        if not link:
            return JsonResponse({'error': 'Link parameter is required'}, status=400)

        try:
            video_id = extract_video_id(link)
            video_info = get_video_info(api_key, video_id)

            # Fetch available formats and qualities using yt-dlp
            ydl_opts = {'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(link, download=False)
                formats = info_dict.get('formats', [])

            # Extract and format available qualities
            quality_list = []
            for f in formats:
                quality_list.append({
                    'format_id': f.get('format_id', 'unknown'),
                    'format': f.get('format', 'unknown'),
                    'quality': f.get('height', 'unknown')  # YouTube formats include 'height' for video quality
                })

            return JsonResponse({'status': 'success', 'qualities': quality_list, 'video_info': video_info})

        except Exception as e:
            return JsonResponse({'error': f'Failed to retrieve video qualities: {e}'}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def download_video(request):
    """
    Download the video in the specified resolution available.
    """
    if request.method == 'POST':
        link = request.POST.get('link')
        quality = request.POST.get('quality')
        
        if not link:
            return JsonResponse({'error': 'Link parameter is required'}, status=400)
        if not quality:
            return JsonResponse({'error': 'Quality parameter is required'}, status=400)

        filename = f"video-{link[-11:]}.mp4"
        output_file = os.path.join(download_path, filename)

        # Construct the format string based on the selected quality
        format_string = f"bestvideo[height >= {quality}]+bestaudio/best"

        youtube_dl_options = {
            "format": format_string,  # Set format to the selected quality
            "outtmpl": output_file,
        }
        
        try:
            with yt_dlp.YoutubeDL(youtube_dl_options) as ydl:
                ydl.download([link])
            return JsonResponse({"status": "success", "file_path": filename})
        except yt_dlp.utils.DownloadError as de:
            return JsonResponse({'error': f'Download failed: {str(de)}'}, status=500)
        except Exception as e:
            return JsonResponse({'error': f'Download failed: {str(e)}'}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def serve_file(request, filename):
    """
    Serve the downloaded file.
    """
    file_path = os.path.join(download_path, filename)
    
    if not os.path.isfile(file_path):
        raise Http404("File not found")
    
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='video/mp4')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response
