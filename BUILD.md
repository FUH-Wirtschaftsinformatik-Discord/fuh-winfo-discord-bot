# Deployment

## Build

```
docker build -f .\bot.Dockerfile -t rndintusr/fuh-winfo-discordbot:v1.1.2 .
docker push rndintusr/fuh-winfo-discordbot:v1.1.2

docker build -f .\scraper.Dockerfile -t rndintusr/fuh-winfo-discordbot-grade-scraper:v1.0.1 .
docker push rndintusr/fuh-winfo-discordbot-grade-scraper:v1.0.1

docker build -f .\plotter.Dockerfile -t rndintusr/fuh-winfo-discordbot-grade-plotter:v1.0.3 .
docker push rndintusr/fuh-winfo-discordbot-grade-plotter:v1.0.3
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