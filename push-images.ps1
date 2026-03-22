docker build -f .\bot.Dockerfile -t rndintusr/fuh-winfo-discordbot:v1.1.13 .
docker push rndintusr/fuh-winfo-discordbot:v1.1.13

docker build -f .\scraper.Dockerfile -t rndintusr/fuh-winfo-discordbot-grade-scraper:v1.1.13 .
docker push rndintusr/fuh-winfo-discordbot-grade-scraper:v1.1.13

docker build -f .\plotter.Dockerfile -t rndintusr/fuh-winfo-discordbot-grade-plotter:v1.1.13 .
docker push rndintusr/fuh-winfo-discordbot-grade-plotter:v1.1.13