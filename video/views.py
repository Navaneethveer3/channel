from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import requests
import os
import yt_dlp

# Directory where downloaded videos will be saved
download_path = os.path.join(os.getcwd(), "media")

# Ensure the download path exists
os.makedirs(download_path, exist_ok=True)

def myproject(request):
    return render(request, 'myproject.html')

def get_video_info(api_key, video_id):
    url = f'https://www.googleapis.com/youtube/v3/videos?id={video_id}&key=AIzaSyD_znizOfuO62ZLybi1vXfM-IyWgA8ymQ8&part=contentDetails,snippet'
    response = requests.get(url)
    data = response.json()
    
    if 'items' in data and len(data['items']) > 0:
        video_info = data['items'][0]
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
        api_key = 'AIzaSyD_znizOfuO62ZLybi1vXfM-IyWgA8ymQ8'  # Replace with your YouTube Data API key
        
        if not link:
            return JsonResponse({'error': 'Link parameter is required'}, status=400)

        try:
            video_id = link.split('v=')[-1]  # Extract video ID from URL
            video_info = get_video_info(api_key, video_id)
            
            # This is a placeholder for formats, since YouTube Data API doesn't provide video quality details
            # You would need to integrate this with another method to get exact formats if required
            quality_list = [{
                'format_id': 'unknown',
                'format': 'unknown',
                'quality': 'unknown'
            }]
            
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
