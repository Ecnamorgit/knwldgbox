import sys
import asyncio
import json

# Trust the OS certificate store so HTTPS works behind antivirus/VPN TLS
# inspection (e.g. Avast Web Shield) that intercepts the Google API calls.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from ghunt.helpers.utils import get_httpx_client
from ghunt.apis.peoplepa import PeoplePaHttp
from ghunt.helpers import auth, playgames, gmaps, calendar as gcalendar
from ghunt.objects.encoders import GHuntEncoder
from ghunt.parsers.people import Person

# Monkey-patch the Person._scrape method in-memory to fix the Google API KeyError bug
original_person_scrape = Person._scrape
async def patched_person_scrape(self, as_client, person_data: dict):
    def fix_metadata(data):
        if isinstance(data, dict):
            if "metadata" in data and isinstance(data["metadata"], dict):
                if "container" not in data["metadata"]:
                    data["metadata"]["container"] = "PROFILE"
            for k, v in data.items():
                fix_metadata(v)
        elif isinstance(data, list):
            for item in data:
                fix_metadata(item)
                
    fix_metadata(person_data)
    return await original_person_scrape(self, as_client, person_data)

Person._scrape = patched_person_scrape

async def main(email_address):
    as_client = get_httpx_client()
    try:
        ghunt_creds = await auth.load_and_auth(as_client)
        people_pa = PeoplePaHttp(ghunt_creds)
        
        is_found, target = await people_pa.people_lookup(as_client, email_address, params_template="max_details")

        if not is_found:
            print("GHUNT_ERROR_START")
            print("not_found")
            print("GHUNT_ERROR_END")
            return
            
        player_results = await playgames.search_player(ghunt_creds, as_client, email_address)
        player = None
        if player_results:
            _, player = await playgames.get_player(ghunt_creds, as_client, player_results[0].id)
            
        err, stats = await gmaps.get_reviews(as_client, target.personId)
        
        cal_found, calendar, calendar_events = await gcalendar.fetch_all(ghunt_creds, as_client, email_address)
        
        container = "PROFILE"
        json_results = {
            f"{container}_CONTAINER": {
                "profile": target,
                "play_games": player if player_results else None,
                "maps": {
                    "photos": None,
                    "reviews": None,
                    "stats": stats
                },
                "calendar": {
                    "details": calendar,
                    "events": calendar_events
                } if cal_found else None
            }
        }
        
        print("GHUNT_JSON_START")
        print(json.dumps(json_results, cls=GHuntEncoder))
        print("GHUNT_JSON_END")
    except Exception as e:
        print("GHUNT_ERROR_START")
        print(f"unknown: {str(e)}")
        print("GHUNT_ERROR_END")
    finally:
        await as_client.aclose()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(main(sys.argv[1]))
