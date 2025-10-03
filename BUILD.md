# Deployment

## Build

```
docker build -f .\bot.Dockerfile -t rndintusr/fuh-winfo-discordbot:v1.1.0 .
docker push rndintusr/fuh-winfo-discordbot:v1.1.0


docker build -f .\scraper.Dockerfile -t rndintusr/fuh-winfo-discordbot-grade-scraper:v1.0.0 .
docker push rndintusr/fuh-winfo-discordbot-grade-scraper:v1.0.0

docker build -f .\plotter.Dockerfile -t rndintusr/fuh-winfo-discordbot-grade-plotter:v1.0.0 .
docker push rndintusr/fuh-winfo-discordbot-grade-plotter:v1.0.0
```

## Run 

```
sudo systemctl daemon-reload
sudo systemctl enable --now test-scraper.timer
sudo systemctl status test-scraper.timer

sudo systemctl daemon-reload
sudo systemctl enable --now test-plotter.timer
sudo systemctl status test-plotter.timer

systemctl list-timers  --all
```