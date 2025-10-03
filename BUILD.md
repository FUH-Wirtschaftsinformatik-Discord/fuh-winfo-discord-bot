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
sudo systemctl enable --now myapp-compose.timer
sudo systemctl status myapp-compose.timer
```