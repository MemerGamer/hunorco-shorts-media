# hunorco-shorts-media

Videos for the daily "IT in 45 seconds" shorts by Kovács Bálint-Hunor ([hunorco.de](https://hunorco.de)),
served through GitHub Pages so the scheduler can fetch them.

- `schedule.json` — one short per day at 10:00 Europe/Bucharest, with the YouTube, TikTok and Instagram captions.
- `videos/` — the MP4s.
- `autopost.py` — run daily by `.github/workflows/autopost.yml`; keeps each Buffer channel's queue filled
  (10 scheduled posts on the free plan) and fails the run if a post could not be published.

Music in each video is CC0 or public domain; the credit is in every caption.
