import json
from airflow.sdk import Variable
from spotipy.cache_handler import CacheHandler

class AirflowCacheHandler(CacheHandler):
    """
    A Spotipy cache handler that uses Airflow Variables to store the token cache.
    """
    def __init__(self, var_name="SPOTIFY_TOKEN_CACHE"):
        self.var_name = var_name

    def get_cached_token(self):
        """
        Gets the token info from an Airflow Variable.
        """
        token_info_json = Variable.get(self.var_name, default=None)
        if token_info_json:
            return json.loads(token_info_json)
        return None

    def save_token_to_cache(self, token_info):
        """
        Saves the token info to an Airflow Variable.
        """
        Variable.set(self.var_name, json.dumps(token_info))
