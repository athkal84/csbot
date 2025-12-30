FROM python:3.10-slim

WORKDIR app

COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 10000

CMD ["rasa", "run", "--enable-api", "--cors", "*", "--port", "10000"]