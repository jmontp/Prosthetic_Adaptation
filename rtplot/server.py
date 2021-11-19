#Import communication
import zmq

#Import plotting
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg

#Common imports 
import numpy as np 
import json
from time import perf_counter
from collections import OrderedDict


#Create connection layer
context = zmq.Context()
# socket = context.socket(zmq.SUB)
socket = context.socket(zmq.PULL)
socket.bind("tcp://*:5555")
#socket.connect("tcp://127.0.0.1:5555")
#socket.connect("tcp://10.0.0.200:5555")
# socket.setsockopt_string(zmq.SUBSCRIBE, "")


### START QtApp #####
# you MUST do this once (initialize things)
app = QtGui.QApplication([])            
# ####################

# width of the window displaying the curve
WINDOW_WIDTH = 200                      

# window title
WINDOW_TITLE = "Real Time Plotter"


ROW = True

#win = pg.GraphicsLayoutWidget(title=WINDOW_TITLE, show=True)

#Create the plot from the json file that is passed in
def initialize_plot(json_config):
    
    #Set background white
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')

    #Define the window
    win = pg.GraphicsLayoutWidget(title=WINDOW_TITLE, show=True) # creates a window
    # if ROW == True:
    #     item = 1
    #     counter = 0
    #     while item is not None:
    #         item = win.getItem(counter,0)
    #         win.removeItem(item)
    # else:
    #     item = 1
    #     counter = 0
    #     while item is not None:
    #         item = win.getItem(0,counter)
    #         win.removeItem(item)
    
    #Array of number per plot and array of pointer to plots
    subplot_per_plot = []
    subplots = []

    num_plots = 0
    top_plot = None
    top_plot_title = ""
    for plot_num, plot_description in enumerate(json_config.values()):
        
        #Add a plot
        num_plots += 1

        #Get the trace names for this plot
        trace_names = plot_description['names']

        #Count how many traces we want
        num_traces = len(trace_names)
        
        #Add the indices in the numpy array
        subplot_per_plot.append(num_traces)

        #Initialize the new plot
        new_plot = win.addPlot()
        
        #Move to the next row
        if ROW == True:
            win.nextRow()
        else:
            win.nextCol()

        #Capture the first plot
        if top_plot == None:
            top_plot = new_plot

        #Add the names of the plots to the legend
        new_plot.addLegend()

        axis_label_style = {'font-size':'20pt'}
        #Add the axis info
        if 'xlabel' in plot_description:
            new_plot.setLabel('bottom', plot_description['xlabel'],**axis_label_style)

        if 'ylabel' in plot_description:
            new_plot.setLabel('left', plot_description['ylabel'],**axis_label_style)

        #Potential performance boost
        new_plot.setXRange(0,WINDOW_WIDTH)

        #Get the y range
        if 'yrange' in plot_description:
            new_plot.setYRange(*plot_description['yrange'])
        
        #Set axis tick mark size
        font=QtGui.QFont()
        font.setPixelSize(50)
        new_plot.getAxis("left").tickFont = font

        font=QtGui.QFont()
        font.setPixelSize(50)
        new_plot.getAxis("bottom").tickFont = font

        #Add title
        title_style = {'size':'25pt'}
        if 'title' in plot_description:
            new_plot.setTitle(plot_description['title'],**title_style)
            
            if plot_num == 0:
                top_plot_title = plot_description['title']

        #Define default Style
        colors = ['r','g','b','c','m','y']
        if 'colors' in plot_description:
            colors = plot_description['colors']

        line_style = [QtCore.Qt.SolidLine] * num_traces
        if 'line_style' in plot_description:
            line_style = [QtCore.Qt.DashLine if desc == '-' else QtCore.Qt.SolidLine for desc in plot_description['line_style']]

        line_width = [1] * num_traces
        if 'line_width' in plot_description:
            line_width = plot_description['line_width']


        for i in range(num_traces):
            #Add the plot object
            pen = pg.mkPen(color = colors[i], style=line_style[i], width=line_width[i])
            new_curve = pg.PlotCurveItem(name=trace_names[i], pen=pen)
            new_plot.addItem(new_curve)
            subplots.append(new_curve)

    print("Initialized Plot!")
    return subplot_per_plot, subplots, num_plots, win, top_plot, top_plot_title


#Receive a numpy array
def recv_array(socket, flags=0, copy=True, track=False):
    """recv a numpy array"""
    md = socket.recv_json(flags=flags)
    msg = socket.recv(flags=flags, copy=copy, track=track)
    buf = memoryview(msg)
    A = np.frombuffer(buf, dtype=md['dtype'])
    return A.reshape(md['shape'])


#Create definitions 
RECEIVED_PLOT_UPDATE = 0
RECEIVED_DATA = 1

#Define function to detect category
def rec_type():
    #Sometimes we get miss-aligned data
    #In this case just ignore the data and wait until you have a valid type
    while True:
        try:
            return int(socket.recv_string())
        except ValueError:
            print("Had a value error")
            pass

try:
    while True:
        #Receive the type of information
        category = rec_type()

        #Do not continue unless you have initialized the plot
        if(category == RECEIVED_PLOT_UPDATE):
            
            #Receive plot configuration
            flags = 0 
            plot_configuration = socket.recv_json(flags=flags)

            #Initialize plot
            subplot_per_plot, subplots, num_plots, win, top_plot, top_plot_title = initialize_plot(plot_configuration)
            
            #Initialize data buffer
            Xm = np.zeros((sum(subplot_per_plot),WINDOW_WIDTH))    

            #Everything is initialized
            initialized_plot = True

            #Define fps variable
            fps = None

            #Get last time to estimate fps
            lastTime = perf_counter()

           
        #Read some data and plot it
        elif (category == RECEIVED_DATA):

            #Read in numpy array
            receive_np_array = recv_array(socket)
            #Get how many new values are in it
            num_values = receive_np_array.shape[1]    

            #Remember how much you need to offset per plot
            subplot_offset = 0

            #Estimate fps
            now = perf_counter()
            dt = now - lastTime
            lastTime = now

            #Calculate the fps
            if fps is None:
                fps = 1.0/dt
            else:
                s = np.clip(dt*3., 0, 1)
                fps = fps * (1-s) + (1.0/dt) * s

            #Plot for every subplot
            for plot_index in range(num_plots):
                
                for subplot_index in range(subplot_per_plot[plot_index]):
                    i = subplot_offset + subplot_index
                    Xm[i,:-num_values] = Xm[i,num_values:]    # shift data in the temporal mean 1 sample left
                    Xm[i,-num_values:] = receive_np_array[i,:]              # vector containing the instantaneous values  
                    subplots[i].setData(Xm[i,:])
                
                #Update before the next loop
                subplot_offset += subplot_per_plot[plot_index]

            #Update fps in title
            top_plot.setTitle(top_plot_title + f" - FPS:{fps:.0f}")
            #Indicate you MUST process the plot now
            QtGui.QApplication.processEvents()    

          

except KeyboardInterrupt:

    try: 
        win
        print("You can move around the plot now")
        QtGui.QApplication.instance().exec_()
    except:
       print("\nNo plot - killing server")


#References
#ZMQ Example code
#https://zeromq.org/languages/python/

#How to send/receive numpy arrays
#https://pyzmq.readthedocs.io/en/latest/serialization.html

#How to real time plot with pyqtgraph
#https://stackoverflow.com/questions/45046239/python-realtime-plot-using-pyqtgraph
