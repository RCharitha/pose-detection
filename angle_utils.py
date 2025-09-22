import math

def calculate_angle(a, b, c):
    
    a = (a.x, a.y)
    b = (b.x, b.y)
    c = (c.x, c.y)


    ab = (a[0] - b[0], a[1] - b[1])
    cb = (c[0] - b[0], c[1] - b[1])


    dot_product = ab[0] * cb[0] + ab[1] * cb[1]
    mag_ab = math.sqrt(ab[0]**2 + ab[1]**2)
    mag_cb = math.sqrt(cb[0]**2 + cb[1]**2)

    if mag_ab == 0 or mag_cb == 0:
        return 0

   
    cos_angle = max(min(dot_product / (mag_ab * mag_cb), 1.0), -1.0)

    angle = math.degrees(math.acos(cos_angle))
    return angle

