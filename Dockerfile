FROM python:3.6

RUN ( \
      apt-get update && \
      apt-get install -y libsasl2-dev python-dev libldap2-dev libssl-dev \
    )

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN pip install pipenv

COPY . /usr/src/app

RUN pipenv install --skip-lock --system --deploy

WORKDIR "/usr/src/app"
ENTRYPOINT ["./manage.py"]
CMD ["runserver","-h","0.0.0.0","-p","80"]

EXPOSE 80
