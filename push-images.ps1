docker build -f .\bot.Dockerfile -t rndintusr/fuh-winfo-discordbot:v1.3.2 .
docker push rndintusr/fuh-winfo-discordbot:v1.3.2

docker build -f .\scraper.Dockerfile -t rndintusr/fuh-winfo-discordbot-grade-scraper:v1.3.2 .
docker push rndintusr/fuh-winfo-discordbot-grade-scraper:v1.3.2

docker build -f .\plotter.Dockerfile -t rndintusr/fuh-winfo-discordbot-grade-plotter:v1.3.2 .
docker push rndintusr/fuh-winfo-discordbot-grade-plotter:v1.3.2