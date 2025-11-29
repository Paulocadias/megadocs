import argparse
import os
import time
import requests
import sys
from pathlib import Path

API_URL = "http://127.0.0.1:8080/api/batch/convert"

def bulk_convert(directory, output_dir, webhook_url=None):
    """
    Zip directory, upload to API, and save result.
    """
    directory = Path(directory)
    output_dir = Path(output_dir)
    
    if not directory.exists():
        print(f"Error: Directory {directory} does not exist.")
        return

    print(f"Processing directory: {directory}")
    
    # Create ZIP of directory
    import shutil
    zip_path = shutil.make_archive("temp_upload", 'zip', directory)
    
    try:
        with open(zip_path, 'rb') as f:
            files = {'file': ('upload.zip', f, 'application/zip')}
            data = {}
            if webhook_url:
                data['webhook_url'] = webhook_url
            
            print("Uploading to API...")
            response = requests.post(API_URL, files=files, data=data)
            
            if response.status_code == 200:
                print("Conversion successful. Downloading result...")
                output_dir.mkdir(parents=True, exist_ok=True)
                output_file = output_dir / f"converted_{int(time.time())}.zip"
                with open(output_file, 'wb') as out_f:
                    out_f.write(response.content)
                print(f"Saved to {output_file}")
            elif response.status_code == 202:
                print("Batch accepted. Result will be sent to webhook.")
            else:
                print(f"Error: {response.status_code} - {response.text}")
                
    except Exception as e:
        print(f"Failed: {e}")
    finally:
        os.remove(zip_path)

def watch_directory(directory, output_dir):
    """
    Watch directory for new files and convert them.
    (Simplified implementation using polling)
    """
    print(f"Watching {directory} for new files...")
    seen_files = set()
    
    while True:
        current_files = set(os.listdir(directory))
        new_files = current_files - seen_files
        
        if new_files:
            print(f"Detected {len(new_files)} new files.")
            # In a real scenario, we'd batch them or process individually.
            # Here we just trigger a bulk convert of the whole dir for demo.
            bulk_convert(directory, output_dir)
            seen_files = current_files
            
        time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DocsSite Automation CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # Bulk Convert
    convert_parser = subparsers.add_parser("convert", help="Bulk convert a directory")
    convert_parser.add_argument("directory", help="Input directory")
    convert_parser.add_argument("--output", "-o", default="./output", help="Output directory")
    convert_parser.add_argument("--webhook", "-w", help="Webhook URL")
    
    # Watch
    watch_parser = subparsers.add_parser("watch", help="Watch directory for changes")
    watch_parser.add_argument("directory", help="Input directory")
    watch_parser.add_argument("--output", "-o", default="./output", help="Output directory")
    
    args = parser.parse_args()
    
    if args.command == "convert":
        bulk_convert(args.directory, args.output, args.webhook)
    elif args.command == "watch":
        watch_directory(args.directory, args.output)
    else:
        parser.print_help()
