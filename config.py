import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    MONGO_URI = os.environ.get('MONGO_URI')
    GOOGLE_MAPS_API_KEY= os.environ.get('GOOGLE_MAPS_API_KEY')
    GOOGLE_MAPS_MAP_ID= os.environ.get('GOOGLE_MAPS_MAP_ID')