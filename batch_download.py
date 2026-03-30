import os, re, csv, sys, msvcrt, argparse, unicodedata
from functions import read_exportify_csv_file, download_spotify_song

sys.stdout.reconfigure(encoding='utf-8')


def run(csv_folder, output_base, audio_format="mp3", platform="youtube"):
    """
    Entry point called from menu.py (or directly from CLI).
    All config comes in as arguments instead of being hardcoded.
    """

    print("Controls:")
    print("  S = Skip current album")
    print("  P = Pause / Resume")
    print("  Q = Quit downloader\n")

    # os.scandir() does not guarantee order, so Unicode filenames can appear randomly, sort them before the loop to normalise names and
    # pass in the csv folder 
    entries = sorted(os.scandir(csv_folder), key=lambda e: unicodedata.normalize("NFC", e.name).casefold())

    # Find resume index automatically (if nothing is downloaded, it returns the index of first folder)
    start_index = find_resume_album(entries, output_base, csv_folder)

    # collect failed tracks for review at the end, the csv gets saved in the output folder
        # e.g. If the output folder is "albums" for C:\albums\<folder_for_each_album> the csv gets saved in the "albums" folder
    skipped_songs = []

    # Loop starting from the resume index
    for entry in entries[start_index:]:

        # define csv file and normalise the file name
        csv_file = unicodedata.normalize("NFC", entry.name)
        if not csv_file.lower().endswith(".csv"):
            continue
        
        # set the album name, use regex to catch special characters and join them on the folder's name on the output dir exactly as the album name
        album_name = re.sub(r'[<>:"/\\|?*]', '', os.path.splitext(csv_file)[0])
        album_output_folder = os.path.join(output_base, album_name)
        os.makedirs(album_output_folder, exist_ok=True)

        print(f"\nProcessing album: {album_name}\n")

        # define the csv path, and call the read_exportify_csv_file function, to read and extract spotify file data into the song variable
        csv_path = os.path.join(csv_folder, csv_file)
        songs = read_exportify_csv_file(csv_path)
        songs = sorted(songs, key=lambda s: int(s.get("track_number", 0)))

        # then for each track in an album, count em starting from 1
        for i, song in enumerate(songs, 1):

            # skip an album if the user types 's', or quit if the user types 'q'
            action = check_keyboard()
            if action == "skip":
                break
            if action == "quit":
                save_skipped(skipped_songs, output_base)
                return

            # Skip already downloaded tracks, in the output folder, check if the track_name and artist_names already exists
            # if it already exists in the album to check, skip that song/album entirely
            final_file = os.path.join(album_output_folder, f"{song['track_name']} - {', '.join(song['artist_names'])}.{audio_format}")
            if os.path.exists(final_file):
                print(f"Skipping already downloaded: {song['track_name']}")
                continue

            # for each album and song in the album, call download_spotify_song with the metadata that it needs, and log any error
            print(f"Downloading {i}/{len(songs)}: {song['track_name']}")
            try:
                download_spotify_song(
                    format=audio_format,
                    metadata=song,
                    output_path=album_output_folder,
                    cookiefile=None,
                    platform=platform
                )
            except Exception as e:
                # fallback to YouTube search if using ytmusic
                if platform == "ytmusic":
                    print(f"ytmusic failed for {song['track_name']}, retrying with YouTube...")
                    try:
                        download_spotify_song(
                            format=audio_format,
                            metadata=song,
                            output_path=album_output_folder,
                            cookiefile=None,
                            platform="youtube"
                        )
                    except Exception as e2:
                        print(f"Failed again: {e2}")
                        skipped_songs.append({
                            "album": album_name,
                            "track": song['track_name'],
                            "artist": ', '.join(song['artist_names']),
                            "error": str(e2)
                        })
                else:
                    skipped_songs.append({
                        "album": album_name,
                        "track": song['track_name'],
                        "artist": ', '.join(song['artist_names']),
                        "error": str(e)
                    })

    save_skipped(skipped_songs, output_base)
    print("\nAll downloads completed.")

# ------------------------------------ Helpers from here ------------------------------------

# this is for checking keystrokes for skipping, pausing and quitting the batch download sscript
def check_keyboard():
    
    # if any of the declared keys are hit, behave accordingly
    if msvcrt.kbhit():
        key = msvcrt.getch().lower()

        if key == b's':
            print("\nSkipping current album...\n")
            return "skip"

        if key == b'q':
            print("\nQuitting downloader...\n")
            return "quit"

        if key == b'p':
            print("\nPaused. Press P again to continue.")
            
            # while the program is paused, if 'p' is hit again, resume the program
            while True:
                if msvcrt.kbhit():
                    if msvcrt.getch().lower() == b'p':
                        print("Resuming...\n")
                        return None

    return None
    
    
def find_resume_album(entries, output_base, csv_folder):

    """ Returns the index in csv_entries to start from. Looks for the first album folder that is missing or incomplete. """

    for idx, entry in enumerate(entries):
        csv_file = unicodedata.normalize("NFC", entry.name)
        if not csv_file.lower().endswith(".csv"):
            continue
        
        album_name = re.sub(r'[<>:"/\\|?*]', '', os.path.splitext(csv_file)[0])
        album_output_folder = os.path.join(output_base, album_name)
        album_output_folder = os.path.join(output_base, album_name)

        # If folder doesn't exist, start here
        if not os.path.exists(album_output_folder):
            return idx
        
        # Count existing files
        existing_files = [f for f in os.listdir(album_output_folder)
                          if f.lower().endswith((".mp3", ".m4a", ".flac"))]

        # Count tracks in CSV
        songs = read_exportify_csv_file(os.path.join(csv_folder, csv_file))
        if len(existing_files) < len(songs):
            return idx  # partially downloaded, resume here

    # All albums complete
    return len(entries)

def save_skipped(skipped_songs, output_base):

    """ Tracked skipped/failed songs or albums and put them in a csv for later review """

    if skipped_songs:
        path = os.path.join(output_base, "skipped_songs.csv")

        # write to the list with a bunch of dicts what was skipped and their details
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["album", "track", "artist", "error"])
            writer.writeheader()
            writer.writerows(skipped_songs)
        print(f"\nSkipped/failed songs logged to: {path}")
    else:
        print("\nNo songs were skipped or failed.")
 
# CLI entry point, also keeps the script runnable standalone
if __name__ == "__main__":
    # using parser, enable the user to provide flags and get specific functionality instead of running the whole script again.
    parser = argparse.ArgumentParser(description="SpotFetch batch downloader")
    parser.add_argument("--csv-folder", "-c", required=True, help="Folder containing Exportify CSVs")
    parser.add_argument("--output", "-o", required=True, help="Output base directory")
    parser.add_argument("--format", "-f", default="mp3", choices=["mp3", "m4a", "flac"])
    parser.add_argument("--platform", "-p", default="youtube", choices=["youtube", "ytmusic"])
    args = parser.parse_args()

    run(
        csv_folder=args.csv_folder,
        output_base=args.output,
        audio_format=args.format,
        platform=args.platform,
    )