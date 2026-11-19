import pygame
import math
import colorsys

pygame.init()

SCALE = 3
W, H = 390, 170
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Nova — Smooth Pill Preview")
clock = pygame.time.Clock()

surface = pygame.Surface((W*SCALE, H*SCALE), pygame.SRCALPHA)
phase = 0.0

def sc(v):
    return int(round(v*SCALE))

def mix(a, b, t):
    t = max(0, min(1, t))
    A = tuple(int(a[i:i+2], 16) for i in (1, 3, 5))
    B = tuple(int(b[i:i+2], 16) for i in (1, 3, 5))
    return tuple(round(A[i]*(1-t)+B[i]*t) for i in range(3))

def neon(t):
    t %= 1
    if t < .34:
        return mix("#00E5FF", "#D500F9", t/.34)
    if t < .68:
        return mix("#D500F9", "#7C4DFF", (t-.34)/.34)
    return mix("#7C4DFF", "#00E5FF", (t-.68)/.32)

def point(x, y):
    return sc(x), sc(y)

def ribbon(t, v, ph):
    # Twisted figure-eight surface
    x = 32*math.sin(t)
    y = 19*math.sin(2*t)
    nx = math.cos(t)*math.cos(t/2+ph)
    ny = -math.sin(t)*math.cos(t/2+ph)
    nz = math.sin(t/2+ph)
    z = 10*math.cos(t+ph)
    return x+v*nx, y+v*ny, z+v*nz

def project(p):
    x, y, z = p
    return 105+x+z*.25, 84+y-z*.20

def draw_glow_line(target, points, color, width):
    # Multiple translucent strokes simulate soft neon bloom
    for extra, alpha in [(8, 16), (5, 24), (2, 48)]:
        glow = pygame.Surface(target.get_size(), pygame.SRCALPHA)
        pygame.draw.lines(
            glow, (*color, alpha), False,
            [point(x, y) for x, y in points],
            sc(width+extra)
        )
        target.blit(glow, (0, 0))
    pygame.draw.lines(
        target, (*color, 245), False,
        [point(x, y) for x, y in points],
        max(1, sc(width))
    )

def draw():
    global phase
    surface.fill((0, 0, 0, 0))

    # Shadow
    shadow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(
        shadow, (0, 0, 0, 150),
        (sc(83), sc(54), sc(224), sc(72)),
        border_radius=sc(36)
    )
    surface.blit(shadow, (0, sc(4)))

    # Outer pill: exactly 220 x 68
    pygame.draw.rect(
        surface, (0, 0, 0, 255),
        (sc(85), sc(50), sc(220), sc(68)),
        border_radius=sc(34)
    )
    pygame.draw.line(
        surface, (38, 38, 42, 220),
        point(119, 51), point(271, 51), sc(.7)
    )

    # Ribbon: multiple smooth continuous paths
    for j in range(17):
        v = -9 + 18*j/16
        pts = []
        for i in range(241):
            t = 2*math.pi*i/240
            pts.append(project(ribbon(t, v, phase)))

        col = neon(j/16*.55 + .1)
        draw_glow_line(surface, pts, col, 0.65)

    # Stronger luminous outer ridges
    for v, shift in [(-9, 0.0), (9, .18)]:
        pts = [
            project(ribbon(2*math.pi*i/240, v, phase))
            for i in range(241)
        ]
        draw_glow_line(surface, pts, neon(shift+phase*.04), 1.0)

    # Inner capsule: exactly 105 x 46
    pygame.draw.rect(
        surface, (15, 15, 18, 255),
        (sc(185), sc(61), sc(105), sc(46)),
        border_radius=sc(23)
    )
    pygame.draw.line(
        surface, (100, 100, 108, 190),
        point(205, 62), point(269, 62), sc(.7)
    )

    # Waveform: four rounded bars and one central dot
    for x, height in [(204, 8), (215, 15), (244, 15), (255, 8)]:
        pygame.draw.line(
            surface, (255, 255, 255, 255),
            point(x, 84-height/2), point(x, 84+height/2),
            sc(1.7)
        )

    pygame.draw.circle(surface, (255, 255, 255), point(230, 84), sc(1.7))

    # Microphone icon at right
    pygame.draw.rect(
        surface, (255, 255, 255, 255),
        (sc(269), sc(73), sc(6), sc(12)),
        border_radius=sc(3)
    )
    pygame.draw.arc(
        surface, (255, 255, 255, 255),
        (sc(265), sc(75), sc(14), sc(17)),
        math.pi, 2*math.pi, sc(.8)
    )
    pygame.draw.line(
        surface, (255, 255, 255, 255),
        point(272, 91), point(272, 94), sc(.8)
    )
    pygame.draw.line(
        surface, (255, 255, 255, 255),
        point(268, 94), point(276, 94), sc(.8)
    )

    # Downsample once for smooth edges
    scaled = pygame.transform.smoothscale(surface, (W, H))
    screen.fill((20, 20, 23))
    screen.blit(scaled, (0, 0))
    pygame.display.flip()
    phase += .018

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    draw()
    clock.tick(60)

pygame.quit()
