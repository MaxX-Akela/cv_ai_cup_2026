import time
import cv2 as cv
import numpy as np
import pymurapi as mur

auv = mur.mur_init()
mur_view = auv.get_videoserver()
cap = cv.VideoCapture(1)

MIN_AREA = 300
CENTER_ZONE = 0.2

colors = {
    'yellow': (( 20, 125,  80), ( 47, 255, 255)),
}

def find_color(img, color):

    hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)
    mask = cv.inRange(hsv, color[0], color[1])
    kernel = np.ones((5, 5), np.uint8)
    mask = cv.morphologyEx(mask, cv.MORPH_OPEN, kernel)
    mask = cv.morphologyEx(mask, cv.MORPH_CLOSE, kernel)
    c, _ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

    return c

def zone(value, size):

    half = size * CENTER_ZONE / 2

    if value < size / 2 - half:

        return 0
    
    if value > size / 2 + half:

        return 2
    
    return 1



def find_tool(img):

    cntr = find_color(img, colors['yellow'])

    cntr = [c for c in cntr if cv.contourArea(c) >= MIN_AREA]

    if not cntr:

        return None

    cnt = max(cntr, key=cv.contourArea)

    m = cv.moments(cnt)

    if m['m00'] == 0:

        return None
    
    cx = int(m['m10'] / m['m00'])

    cy = int(m['m01'] / m['m00'])

    horizontal = ('left', 'center', 'right')[zone(cx, img.shape[1])]

    vertical = ('top', 'middle', 'bottom')[zone(cy, img.shape[0])]

    return cx, cy, horizontal, vertical, cnt

def draw(img, result):

    width, height = img.shape[1], img.shape[0]

    half_x = int(width * CENTER_ZONE / 2)

    half_y = int(height * CENTER_ZONE / 2)

    cv.line(img, (width // 2 - half_x, 0), (width // 2 - half_x, height), (255, 255, 255), 1)

    cv.line(img, (width // 2 + half_x, 0), (width // 2 + half_x, height), (255, 255, 255), 1)

    cv.line(img, (0, height // 2 - half_y), (width, height // 2 - half_y), (255, 255, 255), 1)

    cv.line(img, (0, height // 2 + half_y), (width, height // 2 + half_y), (255, 255, 255), 1)

    if result is not None:

        cx, cy, horizontal, vertical, cnt = result

        x, y, w, h = cv.boundingRect(cnt)

        cv.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

        cv.circle(img, (cx, cy), 5, (0, 0, 255), -1)

        cv.putText(img, vertical + " " + horizontal, (10, 25), cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    return img


if __name__ == "__main__":
    last = None
    try:
        while True:

            ok, img = cap.read()

            if not ok:

                time.sleep(0.05)
                continue

            result = find_tool(img)
            mur_view.show(draw(img, result), 0)

            if result is None:

                auv.set_rgb_color(0, 0, 0)
            else:

                auv.set_rgb_color(0, 50, 0)

            state = None if result is None else (result[2], result[3])
            if state != last:
                if result is None:
                    print("инструмент не найден")
                else:
                    print("инструмент:", result[3], result[2], "(x=%d, y=%d)" % (result[0], result[1]))
                last = state

            time.sleep(0.05)

    finally:

        cap.release()
        mur_view.stop()




