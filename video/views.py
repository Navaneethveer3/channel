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
os.makedirs(download_path, exist_ok=True)

def myproject(request):
    return render(request, 'myproject.html')

def extract_video_id(url):
    """Extract video ID from a YouTube URL."""
    match = re.search(r'(?:v=|embed/|youtu.be/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    raise ValueError('Invalid YouTube URL')

def get_video_info(api_key='AIzaSyD_znizOfuO62ZLybi1vXfM-IyWgA8ymQ8', video_id):
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
    """Fetch available video formats and qualities for the given YouTube video URL."""
    if request.method == 'POST':
        link = request.POST.get('link')
        if not link:
            return JsonResponse({'error': 'Link parameter is required'}, status=400)

        try:
            ydl_opts = {
                'referer': 'https://www.youtube.com/',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
                'noplaylist': True,  # Ensure only the single video is processed
                'geo_bypass': True,  # Bypass geographical restrictions
                'no_warnings': True,  # Suppress warnings
                'writeinfojson': False,  # Avoid writing additional metadata files
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(link, download=False)
                formats = info_dict.get('formats', [])

            # Extract and format available qualities
            quality_list = [
                {
                    'format_id': f.get('format_id', 'unknown'),
                    'format': f.get('format', 'unknown'),
                    'quality': f.get('height', 'unknown')
                }
                for f in formats
            ]

            return JsonResponse({'status': 'success', 'qualities': quality_list})

        except Exception as e:
            return JsonResponse({'error': f'Failed to retrieve video qualities: {e}'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def download_video(request):
    """
    Download the video in the specified resolution available and return video info.
    """
    if request.method == 'POST':
        link = request.POST.get('link')
        quality = request.POST.get('quality')
        
        if not link:
            return JsonResponse({'error': 'Link parameter is required'}, status=400)
        if not quality:
            return JsonResponse({'error': 'Quality parameter is required'}, status=400)

        video_id = extract_video_id(link)
        filename = f"video-{video_id}.mp4"
        output_file = os.path.join(download_path, filename)

        format_string = f"bestvideo[height >= {quality}]+bestaudio/best"

        ydl_opts = {
            "format": format_string,
            "outtmpl": output_file,
            'referer': 'https://www.youtube.com/',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'noplaylist': True,
            'geo_bypass': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            
            video_info = get_video_info(api_key, video_id)
            
            return JsonResponse({
                "status": "success",
                "file_path": filename,
                "video_info": video_info
            })
        except yt_dlp.utils.DownloadError as de:
            return JsonResponse({'error': f'Download failed: {str(de)}'}, status=500)
        except Exception as e:
            return JsonResponse({'error': f'Download failed: {str(e)}'}, status=500)
    
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
