![Logo of the project](.images/signature-stationery.png)

# Real Time Plotting with pyqtgraph and zmq

The point of this module is to be able to plot remotely over socket protocols (currently tcp). This is very useful for setting up real time plots given pyqtgraph's performance. 

The neat feature is that the client has full control over the plot by first sending over a configuration file and then sending data. 


# How to use

The first step to plot is to execute the server.py file in the computer that you want to plot. This will wait for a configuration from the client and then plot the subsequent data that is sent over as numpy arrays. 


In order to use this library, you must import the rtplot.client module into your code. The first step is to define the configuration. There are two ways of doing this

## Simple plot configuration

In the simple plot configuration, you only need to send a list of the names of each trace for each plot. In other words, if you wanted to define two plots, one with phase and phase dot plots, and the other with ramp and stride length, the code would be as follows

```
from rtplot import client

#Define a list of names for every plot
plot1_traces = ['phase', 'phase_dot']
plot2_traces = ['ramp','stride_length']

#Aggregate into list
plot_config = [plot1_traces, plot2_traces]

#Tell the server to initialize the plot
client.initialize_plot(plot_config)

#Everytime we send data we must receive data
#to satisfy tcp flow
client.wait_for_reply()  

```

## Complex plot configuration

Additional elements of the plot can be configured from the client side. To do this, you can define a dictionary that contains the configuration of the plot with special keys. Currently, the keys that are supported are the following: 


* 'names' - This defines the names of the traces. Same as how using just the simple plot configuration using lists works.

* 'colors' - Defines the colors for each trace. Should have at least the same length as the number of traces.

* 'line_style' - Defines wheter or not a trace is dotted or not. 
    * '-' - represents dotted line
    * '' - or anything else represents a normal line


* 'title' - Sets the title to the plot
* 'ylabel' - Sets the y label of the plot
* 'xlabel' - Sets the x label of the plot


You only need to specify the things that you want, if the dictionary element is left out then the default value is used. Some example code of how to use this is as follows (it can also be executed by running client.py)

```
from rtplot import client 

#Define a dictionary of items for each plot
plot_1_config = {'names': ['phase', 'phase_dot', 'stride_length'],
                    'title': "Phase, Phase Dot, Stride Length",
                    'ylabel': "reading (unitless)",
                    'xlabel': 'test 1'}
                   
#Anything not specified gets defaulted 

plot_2_config = {'names': [f"gf{i+1}" for i in range(5)],
                    'colors' : ['w' for i in range(5)],
                    'line_style' : ['-','','-','','-'],
                    'title': "Phase, Phase Dot, Stride Length",
                    'ylabel': "reading (unitless)",
                    'xlabel': 'test 2'}

#Aggregate into list  
plot_config = [plot_1_config,plot_2_config]


#Tell the server to initialize the plot
client.initialize_plots(plot_config)

#Everytime we send data we must receive data
#to satisfy tcp flow
client.wait_for_response()
```

## How to send data

Once the plot has been configured, the data is sent as a numpy array. The order of the data in the array is very important and it MUST be sent where the rows have data that corresponds to the same order that the trace names were defined in. For example, in the simple plot configuration code snipet, the traces were defined as follows

```
#Define a list of names for every plot
plot1_traces = ['phase', 'phase_dot']
plot2_traces = ['ramp','stride_length']
```

The corresponding numpy arraw that would be sent would look like




$$
\begin{equation*}
    \text{data} = 
        \begin{bmatrix} 
            phase_0 & \dots & phase_n \\
            phase\_dot_0 & \dots & phase\_dot_n \\
            ramp_0 & \dots & ramp_n \\
            stride_0 & \dots & stride_n
    
        \end{bmatrix}
\end{equation*}
$$
 
Were n is the amount of columns of data that we send over. Note that the rows each correspond to the labels as they are defined and that we do not specify the width of the data block in the plot configuration. This means that we can send over as many columns of information as we want as long as it does not exceed the window width (WINDOW_WIDTH in server.py).

Similarly, for the example in the complex configuration, the data would take the following shape: 

```
#Define a dictionary of items for each plot
plot_1_config = {'names': ['phase', 'phase_dot', 'stride_length'],
                    'title': "Phase, Phase Dot, Stride Length",
                    'ylabel': "reading (unitless)",
                    'xlabel': 'test 1'}

#rest of dict obviated since it does not make a difference
plot_2_config = {'names': [f"gf{i+1}" for i in range(5)]} 
```

$$
\begin{equation*}
    \text{data} = 
        \begin{bmatrix} 
            phase_0 & \dots & phase_n \\
            phase\_dot_0 & \dots & phase\_dot_n \\
            stride_0 & \dots & stride_n\\
            gf_{1_0} & \dots & gf_{1_n} \\
            gf_{2_0} & \dots & gf_{2_n} \\
            gf_{3_0} & \dots & gf_{3_n} \\
            gf_{4_0} & \dots & gf_{4_n} \\
            gf_{5_0} & \dots & gf_{5_n}           
          
        \end{bmatrix}
\end{equation*}
$$
 

 Once the data is formatted appropriately, it is sent to the client by 

 ```
from rtplot import client 


#Format the data as explained above
data = ... 

#Send data to server to plot
client.send_array(data)

#Everytime we send data we must receive data
#to satisfy tcp flow
client.wait_for_response()
 ```