from locust import HttpUser, task, between

class URLShortenerUser(HttpUser):
    host = "https://url-shortener-production-5390.up.railway.app"
    wait_time = between(1, 2)

    def on_start(self):
        # Each user shortens a URL first to get a short code to test with
        response = self.client.post("/shorten", json={
            "long_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        self.short_code = response.json()["short_code"]

    @task(3)
    def redirect(self):
        # Redirect is tested 3x more than shorten (realistic usage)
        self.client.get(f"/{self.short_code}", allow_redirects=False)

    @task(1)
    def shorten(self):
        self.client.post("/shorten", json={
            "long_url": "https://www.github.com/some/random/url"
        })

    @task(1)
    def stats(self):
        self.client.get(f"/stats/{self.short_code}")