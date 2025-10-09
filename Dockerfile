WORKDIR /app
RUN pip install -r requirements.txt
ENV PORT=3478
EXPOSE 3478
ENTRYPOINT ["python"]
CMD ["app.py"]
