from urllib.parse import urljoin

def get_video_url(filename: str) -> str:
    # Base URL where your static files are served
    base_url = "https://marrir.com/static/videos/uploads/"
    
    # Ensure no leading slash in filename
    filename = filename.lstrip("/")
    
    # Return the full video URL
    return urljoin(base_url, filename)
