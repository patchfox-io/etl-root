FROM python:3.12-bookworm

WORKDIR /usr/src/app

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install \
        ca-certificates \
        git && \
    rm -rd /var/lib/apt/lists/

# Install syft
RUN curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin

RUN update-ca-certificates

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "bash" ]