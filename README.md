sudo apt update
sudo apt upgrade -y

sudo apt-get install git python3 python3-pip curl tar bzip2 build-essential tesseract-ocr python3-venv docker.io docker-compose


python3 -m venv venv

source venv/bin/activate

pip install -r requirements.txt

python src/scanner.py 

