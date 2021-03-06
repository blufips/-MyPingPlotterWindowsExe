from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock, mainthread
from kivy_garden.graph import Graph, MeshLinePlot

import threading
import concurrent.futures
from functools import partial
import subprocess
import time
import network_tools

my_network = network_tools.Network() # Create Object for network tools like ping ang tracert

class SetGraph(FloatLayout):
    stop = threading.Event() # Event property to stop all the threading

    def __init__(self, **kwargs):
        super(SetGraph, self).__init__(**kwargs)
        self.on_going = None # Variable for checking if the tracert is ongoing

    def click_start(self):
        """
        This method is to start the graph plot upon click start button
        It initialize the attributes for the graph plot
        """
        if not self.on_going: # Check if the tracert is ongoing. To prevent multiple thread on start
            self.on_going = True
            self.hop_dict = {0: {'time': 0}}
            self.plot = None # Variable for checking if plot is added to graph
            self.traceroute = my_network.my_traceroute(self.ids.host_input.text) # Issue Tracert in external command line and return generator
            self.event1 = Clock.create_trigger(self.update_graph, 0.1) # Create a trigger event of method update_graph to make a repeated check of graph
            self.stop_thread = False # Variable for checking the signal to stop the threading
            self.on_start()

    @mainthread
    def on_start(self, *args):
        """
        This method is to Initialize and start the threading for network_thread
        """
        self.my_thread = threading.Thread(target=self.network_thread) # Create a threading for doing the tracert
        self.my_thread.start() # Start the thread

    def network_thread(self):
        """
        This method is to create threading for the ping and tracert external command
        Threading is used to avoid the GUI to freeze and to speed up I/O
        After checking the current value of tracert or ping it update the graph
        """
        # self.t1 = time.time()
        try: # Try to Iterate to self.traceroute generator if raise exeception issue ping command to all IP in the self.ip_list
            if self.stop_thread: # Check if the thread is need to stop
                return
            current_trace = next(self.traceroute) # Iterate to next tracert
            # Get the value of the dictionary generated by current_trace and added to the hop_dict
            if current_trace['time'] == '0':
                packet_loss = 1
            else:
                packet_loss = 0
            if current_trace['hostname'] == None:
                current_trace['hostname'] = ' '
            # elif len(current_trace['hostname']) > 10:
            #     current_trace['hostname'] = current_trace['hostname'][:10]+'...'
            self.hop_dict[-1*int(current_trace['hop'])] = {'time': int(current_trace['time']),
                                                           'desip': current_trace['desip'],
                                                           'hostname': current_trace['hostname'],
                                                           'count': 1,
                                                           'totaltime': int(current_trace['time']),
                                                           'packetloss': packet_loss,
                                                           'avg': int(current_trace['time'])}
        except StopIteration:
            with concurrent.futures.ThreadPoolExecutor() as executor: # Create concurrent threading to all the ping command
                results = executor.map(my_network.my_ping, [self.hop_dict[hop*-1]['desip'] for hop in range(1,len(self.hop_dict))])
                results = list(results) # Force the results evaluation
            hop_count = -1 # hop counting
            for result in results: # loop to get the generated output of ping
                for ping in result:
                    # print(ping)
                    self.hop_dict[hop_count]['time'] = int(ping['time']) # Set the new self.time_list value
                    self.hop_dict[hop_count]['count'] += 1
                    if ping['rto']:
                        self.hop_dict[hop_count]['packetloss'] += 1
                    self.hop_dict[hop_count]['totaltime'] += int(ping['time'])
                    avg = self.hop_dict[hop_count]['totaltime'] / (self.hop_dict[hop_count]['count']-self.hop_dict[hop_count]['packetloss'])
                    self.hop_dict[hop_count]['avg'] = round(avg)
                    hop_count -= 1
        finally:
            self.event1() # Trigger the method update_graph

    @mainthread
    def update_graph(self, *args):
        """
        This method is to update the plot points of the Graph
        Then check the current value of points in network_thread
        """
        if self.plot: # Check if there are available graph plot to remove
            self.ids['tracert_graph'].remove_plot(self.plot) # Remove the graph plot
            self.ids['tracert_graph']._clear_buffer() # Clear the buffer
        self.plot = MeshLinePlot(color=[1, 0, 0, 1])
        self.plot.points = [(self.hop_dict[num*-1]['time'], num*-1) for num in range(len(self.hop_dict))] # Set the value of plot points
        self.ids.tracert_graph.ymin = -1 * (len(self.hop_dict)-1) # Set the ymin use max hop
        time_list = [self.hop_dict[num]['time'] for num in self.hop_dict]
        self.ids.tracert_graph.xmax = round(max(time_list)*1.1) # Set the xmas use the max value in time_list
        self.ids['tracert_graph'].add_plot(self.plot)
        self.ids.output_grid.clear_widgets() # Clear current label widget in output_grid
        for num in range(1, len(self.hop_dict)): # Loop for adding label widget in output_grid
            num = num*-1
            hop_label = Label(text=str(num*-1), size_hint_x=0.1)
            pl = round(self.hop_dict[num]['packetloss']/self.hop_dict[num]['count']*100, 2)
            pl_label = Label(text=str(pl), size_hint_x=0.1)
            if self.hop_dict[num]['desip'] == 'Request': # Change text Request into RTO
                self.hop_dict[num]['desip'] = 'RTO'
            ip_button = Button(text=self.hop_dict[num]['desip'], size_hint_x=0.3, on_release=partial(self.on_press, self.hop_dict[num]['hostname'], self.hop_dict[num]['desip'], str(num*-1)))
            if len(self.hop_dict[num]['hostname']) > 10: # Cut the letter of host name if the len is morethan 10
                hop_dict = self.hop_dict[num]['hostname'][:10]+'...'
            else:
                hop_dict = self.hop_dict[num]['hostname']
            name_label = Label(text=hop_dict, size_hint_x=0.3, text_size=(self.ids.output_grid.width*0.3, None), halign='center')
            avg_label = Label(text=str(self.hop_dict[num]['avg']), size_hint_x=0.1)
            cur_label = Label(text=str(self.hop_dict[num]['time']), size_hint_x=0.1)
            self.ids.output_grid.add_widget(hop_label)
            self.ids.output_grid.add_widget(pl_label)
            self.ids.output_grid.add_widget(ip_button)
            self.ids.output_grid.add_widget(name_label)
            self.ids.output_grid.add_widget(avg_label)
            self.ids.output_grid.add_widget(cur_label)
        # self.t2 = time.time()
        # print(self.t2 - self.t1)
        self.on_start() # Update the value of plot points from network_thread

    def on_press(self, hostname, desip, hop, *args):
        """
        This method is to open python file ping_new_window.py with argument of hostname, desip and hop
        when the button press on ip_button
        """
        my_args = [hostname, desip, hop]
        subprocess.Popen(['python', 'ping_new_window.py'] + my_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def click_stop(self):
        """
        This method is to check if the tracert is ongoing and start on_stop thread
        """
        if self.on_going == True: # Check if the tracert is on going. To prevent multiple thread on stop
            self.on_going = None
            threading.Thread(target=self.on_stop).start()

    def on_stop(self):
        """
        This method is to stop the tracert function
        It stop the threading and cancel the loop event for updating the graph
        It remove the current graph
        """
        self.ids.output_grid.clear_widgets() # Clear all label widget on output_grid
        self.on_going = None # Set the on_going tracert to None
        self.stop_thread = True
        self.my_thread.join()
        self.event1.cancel()
        if self.plot:
            self.ids['tracert_graph'].remove_plot(self.plot)
            self.ids['tracert_graph']._clear_buffer()

class PingPlotApp(App):

    def build(self):
        my_graph = SetGraph()
        return my_graph

    def on_stop(self):
        self.root.stop.set() # Set a stop signal for secondary threads

if __name__ == '__main__':
    PingPlotApp().run()
