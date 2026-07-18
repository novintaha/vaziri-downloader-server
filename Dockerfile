FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg curl unzip git && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs

RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="/root/.deno/bin:${PATH}"

RUN git clone --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil-provider
WORKDIR /opt/bgutil-provider/server
RUN npm ci && npx tsc

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

RUN chmod +x start.sh

CMD ["./start.sh"]