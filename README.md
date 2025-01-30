sudo apt update
sudo apt upgrade -y

sudo apt-get install git python3 curl tar bzip2 make base-devel build-essential tesseract-ocr python3-venv

python3 -m venv venv

source venv/bin/activate

pip install -r requirements.txt

python src/scanner.py 
