from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import os
import re
import yt_dlp
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

# Directory where downloaded videos will be saved
download_path = os.path.join(os.getcwd(), "media")
os.makedirs(download_path, exist_ok=True)

# Path to your ChromeDriver
CHROMEDRIVER_PATH = '/path/to/chromedriver'

def myproject(request):
    return render(request, 'myproject.html')

def extract_video_id(url):
    """Extract video ID from a YouTube URL."""
    match = re.search(r'(?:v=|embed/|youtu.be/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    raise ValueError('Invalid YouTube URL')

def get_video_info(video_url):
    """
    Fetch video title and duration using Selenium WebDriver.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run headless Chrome
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(video_url)
        time.sleep(3)  # Wait for the page to load

        # Extract video title
        title_element = driver.find_element(By.CSS_SELECTOR, 'meta[name="title"]')
        title = title_element.get_attribute('content') if title_element else 'Unknown Title'

        # Extract video duration
        duration_element = driver.find_element(By.CSS_SELECTOR, 'meta[itemprop="duration"]')
        duration = duration_element.get_attribute('content') if duration_element else 'Unknown Duration'

        return {
            'title': title,
            'duration': duration
        }
    except Exception as e:
        raise ValueError(f'Failed to fetch video info: {e}')
    finally:
        driver.quit()

@csrf_exempt
def get_video_qualities(request):
    """Fetch available video formats and qualities for the given YouTube video URL."""
    if request.method == 'POST':
        link = request.POST.get('link')
        if not link:
            return JsonResponse({'error': 'Link parameter is required'}, status=400)

        try:
            ydl_opts = { 
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'quiet': True,
                'noplaylist': True,
                'geo_bypass': True,
                'referer': 'https://www.youtube.com/',
                'add_header': [('Accept-Language','en-US,en;q=0.9')],
                'force_generic_extractor' : True,
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
            "user_agent" : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36',
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
