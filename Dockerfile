FROM python:3.9-alpine
MAINTAINER Jonathan Kelley <jonk@omg.lol>
ENV DEBIAN_FRONTEND noninteractive
ADD . /app/
WORKDIR /app
RUN apk update && apk add build-base
RUN pip install .  # <- Simply replace this line
RUN mkdir -p /etc/uhppoted
RUN addgroup -g 15000 -S resume && adduser -u 15000 -S resume -G resume
USER resume
EXPOSE 5001
ENTRYPOINT ["doorcontrol"]

