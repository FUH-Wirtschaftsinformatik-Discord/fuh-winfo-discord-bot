docker build -f .\bot.Dockerfile -t rndintusr/fuh-winfo-discordbot:v1.2.0 .
docker push rndintusr/fuh-winfo-discordbot:v1.2.0

docker build -f .\scraper.Dockerfile -t rndintusr/fuh-winfo-discordbot-grade-scraper:v1.2.0 .
docker push rndintusr/fuh-winfo-discordbot-grade-scraper:v1.2.0

docker build -f .\plotter.Dockerfile -t rndintusr/fuh-winfo-discordbot-grade-plotter:v1.2.0 .
docker push rndintusr/fuh-winfo-discordbot-grade-plotter:v1.2.0