import math

def get_last_L2_error(lines,name,LastLines=35) :
   """Get L_2 eror value from a set of lines for the last timestep.
   The set of lines correspond to the output-lines of a flexi-run"""
   for l in lines[-LastLines:] : # read the last XX lines (default is 35)
       # search for name, e.g., "L2_Part" or "L_2"
       if name in l :
           tmp = l.split(":")[1]
   return [float(x) for x in tmp.split()]

def get_last_number_of_timesteps(lines,name,LastLines=35) :
   """Get the number of total timesteps used for the simulation.
   The set of lines correspond to the output-lines of a flexi-run"""
   for l in lines[-LastLines:] : # read the last XX lines (default is 35)
       # search for name, e.g., "#Timesteps"
       if name in l :
           tmp = l.split(":")[1]
   return [float(x) for x in tmp.split()]

def get_initial_timesteps(lines,name) :
   """Get the initial timestep used for the simulation.
   The set of lines correspond to the output-lines of a flexi-run"""
   for l in lines: # read all
       # search for name, e.g., "#Timesteps"
       if name in l :
           tmp = l.split(":")[1]
   return [float(x) for x in tmp.split()]

def get_last_Linf_error(lines,LastLines=35) :
   """Get L_inf eror value from a set of lines for the last timestep
   The set of lines correspond to the output-lines of a flexi-run"""
   for l in lines[-LastLines:] : # read the last XX lines (default is 35)
       if "L_inf" in l :
           tmp = l.split(":")[1]
           return [float(x) for x in tmp.split()]

def get_last_number(lines) :
   for line in reversed(lines) :
       tmp = line.split(' ')
       for t in reversed(tmp) :
           try :
               return float(t)
           except :
               pass

def get_cpu_per_dof(lines) :
   """Get the PID value from a set of lines
   The set of lines correspond to the output-lines of a flexi-run"""
   for line in reversed(lines) :
        if "CALCULATION TIME PER TSTEP/DOF: [" in line :
           return float(line.split("[")[1].split("sec")[0])

def calcOrder_h(h,E,invert_h=False) :
    """Determine the order of convergence for a list of grid spacings h and errors E"""
    if invert_h :
        h = [1./float(elem) for elem in h]
    else :
        h = [float(elem) for elem in h]
    E = [float(elem) for elem in E]
    if len(h) != len(E) :
        return -1

    order = []
    for i in range(1,len(h)) :
        dh=1.0/(h[i]/h[i-1])
        if E[i-1] == 0.0 :
            order.append(0.0)
        else :
            dE=E[i]/E[i-1]
            order.append(math.log(dE)/math.log(dh))

    return order

def calcOrder_p(p,E) :
    """Determine the order of convergence for a list of polynomial degrees p and errors E"""
    p = [float(elem) for elem in p]
    E = [float(elem) for elem in E]
    if len(p) != len(E) :
        return -1

    order = []
    for i in range(1,len(p)) :
        dp=1.0/((p[i]+1.0)/(p[i-1]+1.0))
        if E[i-1] == 0.0 :
            order.append(0.0)
        else :
            dE=E[i]/E[i-1]
            order.append(math.log(dE)/math.log(dp))

    return order
