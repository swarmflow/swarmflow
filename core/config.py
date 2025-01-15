"""
Copyright (c) 2025 Swarmflow
Licensed under Elastic License 2.0 or Commercial License
See LICENSE file for details
"""
from dotenv import load_dotenv
import os
class Config:
    '''
    Configuration for Supabase Configuration and Management.
    '''
    def __init__(self):
        load_dotenv()
        self.OPEN_AI_KEY = os.getenv('OPEN_AI_KEY')
        POSTGRES_USER = os.getenv('POSTGRES_USER')
        POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
        POSTGRES_HOST = os.getenv('POSTGRES_HOST')
        POSTGRES_PORT = os.getenv('POSTGRES_PORT')
        POSTGRES_DB = os.getenv('POSTGRES_DB')
        self.postgres_url = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'
        
        # Redis configuration
        self.REDIS_HOST = os.getenv('REDIS_HOST')
        self.REDIS_PORT = os.getenv('REDIS_PORT')
