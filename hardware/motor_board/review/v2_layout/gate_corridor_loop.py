import math
def area(p):
    return abs(sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p))))/2
def per(p):
    return sum(math.dist(p[i],p[(i+1)%len(p)]) for i in range(len(p)))
N=[(54.7,10.35),(54.4,14.03),(54.4,16.97),(50.9,15.35),(46.5,15.35),(47.87,11.87),(48.5,7.95),(55.34,6.42)]
M=[(49.485,10.35),(46.85,14.03),(46.85,16.97),(50.35,15.35),(54.75,15.35),(54.75,11.87),(55.385,7.95),(50.12,6.42)]
for n,p in (("N (as placed)",N),("M (HS left, LS right)",M)):
    print(n, "area %.1f mm2, perimeter %.1f mm"%(area(p),per(p)))
# board part of the loop over L2: sum mu0*h*len/width, h = 0.069 + 0.035 (copper) ~ 0.1 mm
mu0=4e-7*math.pi
for h in (0.069,0.1,0.21):
    print("h=%.3f mm: 1 square of L1-over-L2 = %.3f nH"%(h,mu0*h*1e-3*1e9))
# L4 slot across the L3 feed: extra = mu0*(d23)*w/l
for w,l in ((1.2,11.0),(1.2,6.0)):
    print("slot w=%.1f l=%.1f: +%.2f nH (return via L2 over the slot)"%(w,l,mu0*1.23e-3*w/l*1e9))
# microstrip pair: gate loop per mm
eps=3.9;w=0.25;hh=0.069
ee=(eps+1)/2+(eps-1)/2*(1+12*hh/w)**-0.5
z0=120*math.pi/(math.sqrt(ee)*(w/hh+1.393+0.667*math.log(w/hh+1.444)))
Lp=z0*math.sqrt(ee)/3e8*1e9/1e3  # nH/mm
print("microstrip w0.25 h0.069: Z0 %.1f ohm, eeff %.2f, L' %.3f nH/mm, pair loop ~%.2f nH/mm"%(z0,ee,Lp,2*Lp*0.97))
C=8.854e-12*eps*0.25e-3*1e-3/0.069e-3
print("trace-to-plane C per mm (parallel plate) %.3f pF/mm"%(C*1e12))
