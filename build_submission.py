import os
import zipfile

def create_submission_zip():
    output_filename = 'SentinelFlow_Final_Submission.zip'
    
    # Remove existing zip if it exists
    if os.path.exists(output_filename):
        os.remove(output_filename)
        
    def should_exclude(filepath):
        # Exclude large file extensions
        if filepath.endswith('.pkl') or filepath.endswith('.csv') or filepath.endswith('.zip') or filepath.endswith('.db'):
            return True
            
        # Exclude hidden and environment directories
        parts = filepath.replace('\\', '/').split('/')
        for exclude_dir in ['.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.ipynb_checkpoints']:
            if exclude_dir in parts:
                return True
                
        return False

    total_size = 0
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            for file in files:
                file_path = os.path.join(root, file)
                if not should_exclude(file_path):
                    # Add to zip
                    arcname = os.path.relpath(file_path, '.')
                    zipf.write(file_path, arcname)
                    total_size += os.path.getsize(file_path)
                    
    print(f"Successfully created {output_filename}")
    print(f"Uncompressed size of included files: {total_size / (1024*1024):.2f} MB")
    print(f"Zip file size: {os.path.getsize(output_filename) / (1024*1024):.2f} MB")

if __name__ == "__main__":
    create_submission_zip()
