from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import os
import re
import yt_dlp
import requests
import json
from googleapiclient.discovery import build

# Directory where downloaded videos will be saved
download_path = os.path.join(os.getcwd(), "media")
os.makedirs(download_path, exist_ok=True)

# ScraperAPI credentials
SCRAPERAPI_KEY = '745e84f86d0ce7981748c263869e87ba'
SCRAPERAPI_URL = "http://api.scraperapi.com"

# YouTube Data API credentials
YOUTUBE_API_KEY = 'AIzaSyD_znizOfuO62ZLybi1vXfM-IyWgA8ymQ8'

def myproject(request):
    return render(request, 'myproject.html')

def extract_video_id(url):
    """Extract video ID from a YouTube URL."""
    match = re.search(r'(?:v=|embed/|youtu.be/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    raise ValueError('Invalid YouTube URL')

def fetch_with_scraperapi(url, params=None):
    """Fetch content from a URL using ScraperAPI."""
    params = params or {}
    params['api_key'] = SCRAPERAPI_KEY
    response = requests.get(SCRAPERAPI_URL, params=params)
    response.raise_for_status()
    return response.text

def get_video_info_from_api(video_id):
    """
    Fetch video title and duration using YouTube Data API.
    """
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.videos().list(
        part='snippet,contentDetails',
        id=video_id
    )
    response = request.execute()
    
    if response['items']:
        item = response['items'][0]
        title = item['snippet']['title']
        duration = item['contentDetails']['duration']
        return {
            'title': title,
            'duration': duration
        }
    return {'title': 'Unknown Title', 'duration': 'Unknown Duration'}

def get_video_info(video_url):
    """
    Fetch video info using ScraperAPI or fallback to YouTube Data API.
    """
    try:
        video_id = extract_video_id(video_url)
        # Attempt to get video info using ScraperAPI
        html_content = fetch_with_scraperapi(video_url, {'url': video_url})
        # Extract video title and duration from HTML
        title_match = re.search(r'<meta name="title" content="(.*?)"', html_content)
        title = title_match.group(1) if title_match else 'Unknown Title'
        duration_match = re.search(r'<meta itemprop="duration" content="(.*?)"', html_content)
        duration = duration_match.group(1) if duration_match else 'Unknown Duration'
        
        # Fallback to YouTube Data API if info is not extracted
        if title == 'Unknown Title' or duration == 'Unknown Duration':
            return get_video_info_from_api(video_id)
        
        return {'title': title, 'duration': duration}
    
    except Exception as e:
        raise ValueError(f'Failed to fetch video info: {e}')

@csrf_exempt
def get_video_qualities(request):
    """Fetch available video formats and qualities for the given YouTube video URL."""
    if request.method == 'POST':
        link = request.POST.get('link')
        if not link:
            return JsonResponse({'error': 'Link parameter is required'}, status=400)

        try:
            ydl_opts = { 
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36',
                'quiet': True,
                'noplaylist': True,
                'geo_bypass': True,
                'referer': 'https://www.youtube.com/',
                'add_header': [('Accept-Language','en-US,en;q=0.9')],
                'force_generic_extractor': True,
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
            "user_agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36',
            "format": format_string,
            "outtmpl": output_file,
            'referer': 'https://www.youtube.com/',
            'noplaylist': True,
            'geo_bypass': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            video_url = f'https://www.youtube.com/watch?v={video_id}'
            video_info = get_video_info(video_url)
            
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
