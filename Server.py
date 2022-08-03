from flask import Flask, render_template, send_from_directory, Response, request, redirect
from pathlib import Path
from capture import capture_and_save
from camera import Camera
import RPi.GPIO as GPIO 
from gpiozero import Robot 
from flask_basicauth import BasicAuth
import argparse, logging, logging.config, conf
import time
import datetime
import threading
import cv2
import board
import dht11
import sys
import argparse
import io
import os
from PIL import Image
import torch
import sqlite3
import distTest

logging.config.dictConfig(conf.dictConfig)
logger = logging.getLogger(__name__)

def getData():
	conn=sqlite3.connect('sensorsData.db')
	curs=conn.cursor()

	for row in curs.execute("SELECT * FROM DHT_data ORDER BY timestamp DESC LIMIT 1;"):
		temp = row[1]
		hum = row[2]
	conn.close()
	return temp, hum

camera = Camera()
camera.run()

app = Flask(__name__)
app.config['BASIC_AUTH_USERNAME'] = 'razvan'
app.config['BASIC_AUTH_PASSWORD'] = 'razvan'
app.config['BASIC_AUTH_FORCE'] = True

basic_auth = BasicAuth(app)
last_epoch = 0
GPIO.setmode(GPIO.BCM)
robby = Robot(left=(27,26), right=(17,22))
robby1 = Robot(left=(21,20), right=(16,12))
GPIO_TRIGGER = 18
GPIO_ECHO = 24
 
GPIO.setup(GPIO_TRIGGER, GPIO.OUT)
GPIO.setup(GPIO_ECHO, GPIO.IN)

@app.after_request
def add_header(r):

	r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
	r.headers["Pragma"] = "no-cache"
	r.headers["Expires"] = "0"
	r.headers["Cache-Control"] = "public, max-age=0"
	return r

@app.route("/")
@basic_auth.required
def entrypoint():
	logger.debug("Requested /")
	temp, hum = getData()
	dist=distTest.main()
	templateData = {
		'temp': temp,
		'hum': hum,
        'dist':dist
	}
	return render_template('index.html', **templateData)

@app.route("/detection", methods=["GET", "POST"])
def predict():
    logger.debug("Requested prediction")
    if request.method == "POST":
        if "file" not in request.files:
            return redirect(request.url)
        file = request.files["file"]
        if not file:
            return

        img_bytes = file.read()
        img = Image.open(io.BytesIO(img_bytes))
        results = model(img, size=640)
        results.render()  
        for img in results.imgs:
            img_base64 = Image.fromarray(img)
            img_base64.save("static/image0.jpg", format="JPEG")
        return redirect("static/image0.jpg")
    return render_template("detection.html")

@app.route("/detec", methods=["GET", "POST"])
def detec():
    logger.debug("Requested detection")
    img = camera.get_frame(_bytes=False)
    results = model(img, size=640)
    results.render()  
    for img in results.imgs:
        img_base64 = Image.fromarray(img)
        img_base64.save("static/image1.jpg", format="JPEG")

    return redirect("static/image1.jpg")
@app.route("/r")
def capture():
	logger.debug("Requested capture")
	im = camera.get_frame(_bytes=False)
	capture_and_save(im)
	return render_template("send_to_init.html")
@app.route("/static")
def last_image():
	logger.debug("Requested last image")
	p = Path("static")
	if p.exists():
		r = "image1.jpg"
	else:
		logger.debug("No last image")
		r = "not_found.jpeg"
	return send_from_directory("static",r)
def gen(camera):
	logger.debug("Starting stream")
	while True:
		frame = camera.get_frame()
		yield (b'--frame\r\n' b'Content-Type: image/png\r\n\r\n' + frame + b'\r\n')

@app.route("/stream")
def stream_page():
	logger.debug("Requested stream page")
	return render_template("index.html")

@app.route("/video_feed")
def video_feed():
	return Response(gen(camera),
		mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/<action>")
def control(action):
    logger.debug("Requested controll")
    if action == "forward":
        robby1.forward()
        robby.forward()
    elif action == "backward":
       robby1.backward()
       robby.backward()
    elif action == "right":
        robby1.right()
        robby.right()
    elif action == "left":
        robby1.left()
        robby.left()
    elif action == "stop":
        robby.stop()
        robby1.stop()
    
   
    return render_template("index.html")

if __name__=="__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument('-p','--port',type=int,default=5000, help="Running port")
	parser.add_argument("-H","--host",type=str,default='192.168.0.104', help="Address to broadcast")
	args = parser.parse_args()
	model = torch.hub.load("ultralytics/yolov5", "yolov5s", pretrained=True, force_reload=True, autoshape=True)
	model.eval()#reîncărcare forțată
	logger.debug("Starting server")
	app.run(host=args.host,port=args.port)
