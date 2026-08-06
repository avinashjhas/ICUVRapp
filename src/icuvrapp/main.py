from dotenv import find_dotenv, load_dotenv

# Load .env BEFORE importing ICUVRstudy, which reads env vars at import time.
# override=True so .env wins over any pre-existing shell/user environment values.
load_dotenv(find_dotenv(), override=True)

from icuvrapp.icuvrstudy import run_app


def main():
    run_app()


if __name__ == "__main__":
    main()
