import time

import cv2 as cv
import numpy as np

import pymurapi as mur

auv = mur.mur_init()
mur_view = auv.get_videoserver()
cap = cv.VideoCapture(0)

TARGET = 'red'
MIN_AREA = 150
CENTER_ZONE = 0.2

colors = {
    'red':    [(  0, 120,  70), (  4, 255, 255), (165, 120,  70), (180, 255, 255)],
    'yellow': (( 20, 125,  80), ( 47, 255, 255)),
    'green':  (( 54, 191, 100), ( 73, 255, 255)),
    'blue':   (( 96, 191,  85), (130, 255, 255)),
}

def find_color(img, color):

    hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)

    mask = cv.inRange(hsv, color[0], color[1])

    for i in range(2, len(color), 2):

        mask = cv.bitwise_or(mask, cv.inRange(hsv, color[i], color[i + 1]))

    kernel = np.ones((3, 3), np.uint8)

    mask = cv.morphologyEx(mask, cv.MORPH_OPEN, kernel)

    mask = cv.morphologyEx(mask, cv.MORPH_CLOSE, kernel)

    c, _ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

    return c

def find_buoy(img, color_name):

    cntr = find_color(img, colors[color_name])

    cntr = [c for c in cntr if cv.contourArea(c) >= MIN_AREA]

    if not cntr:

        return None

    cnt = max(cntr, key=cv.contourArea)

    m = cv.moments(cnt)
    if m['m00'] == 0:
        return None

    cx = int(m['m10'] / m['m00'])

    cy = int(m['m01'] / m['m00'])

    width = img.shape[1]

    half = width * CENTER_ZONE / 2

    if cx < width / 2 - half:

        position = 'left'

    elif cx > width / 2 + half:

        position = 'right'

    else:

        position = 'center'

    return cx, cy, position, cnt


def draw(img, result):
    width, height = img.shape[1], img.shape[0]

    half = int(width * CENTER_ZONE / 2)

    cv.line(img, (width // 2 - half, 0), (width // 2 - half, height), (255, 255, 255), 1)

    cv.line(img, (width // 2 + half, 0), (width // 2 + half, height), (255, 255, 255), 1)

    if result is not None:

        cx, cy, position, cnt = result

        cv.drawContours(img, [cnt], -1, (0, 255, 0), 2)

        cv.circle(img, (cx, cy), 5, (0, 0, 255), -1)

        cv.putText(img, position, (10, 25), cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
    return img


if __name__ == "__main__":
    last = None
    try:
        while True:

            ok, img = cap.read()

            if not ok:
                
                time.sleep(0.05)
                continue

            result = find_buoy(img, TARGET)
            
            mur_view.show(draw(img, result), 0)

            state = None if result is None else result[2]
            
            if state != last:
                
                if result is None:
                
                    print(TARGET, "- буй не найден")
                
                else:
                
                    print(TARGET, "- буй:", result[2], "(x=%d, y=%d)" % (result[0], result[1]))
                
                last = state

            time.sleep(0.05)

    finally:

        cap.release()
        mur_view.stop()
