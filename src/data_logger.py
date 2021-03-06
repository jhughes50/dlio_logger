"""
Author: Jason Hughes
Date: June 2022
DLIO data logger node
"""

import rospy
import csv
import copy
from datetime import datetime
from sensor_msgs.msg import Imu, MagneticField, FluidPressure
from mavros_msgs.msg import State
import pandas as pd

class DataLogger():

    def __init__(self):
        dt = datetime.now()
        time_str = str(dt.month) +'_'+ str(dt.day)+'_'+str(dt.year)+'_'+str(dt.hour)+'_'+str(dt.minute)+'_'+str(dt.second)
        self.csv_out = rospy.get_param('/logger/logger_path') + 'collection_'+time_str+'.csv'
        self.windows = [10,25,50] #[10th, half, one second]

        self.point_types = rospy.get_param('/logger/point_types')
        self.attributes = copy.copy(self.point_types)
        self.imu = Imu()
        self.imu_raw = Imu()
        self.mag = MagneticField()
        self.pressure = FluidPressure()
        self.state = State()

        self.orientation = {'x':0.0, 'y':0.0, 'z':0.0, 'w':0.0}
        self.angular_vel = {'x':0.0, 'y':0.0, 'z':0.0}
        self.linear_accel = {'x':0.0, 'y':0.0, 'z':0.0}
        self.mag_comp = {'x':0.0, 'y':0.0, 'z':0.0}
        self.fluid_pressure = 0.0

        self.sw_rows_10, self.sw_rows_25, self.sw_rows_50 = [], [], []

        rospy.loginfo("DataLogger Init")

        for win in self.windows:
            for att in self.point_types[2:-1]:
                self.attributes.append(str(att)+'_sw_mean_'+str(win))
                self.attributes.append(str(att)+'_sw_std_'+str(win))
                self.attributes.append(str(att)+'_sw_mad_'+str(win))
        
        # write csv header
        with open (self.csv_out,'w') as f:
            writer = csv.writer(f)
            writer.writerow(self.attributes)

        rospy.Subscriber('/mavros/state', State, self.state_cb)
        rospy.Subscriber('/mavros/imu/data', Imu, self.imu_cb)
        rospy.Subscriber('/mavros/imu/data_raw', Imu, self.imu_raw_cb)
        rospy.Subscriber('/mavros/imu/mag', MagneticField, self.mag_cb)
        rospy.Subscriber('/mavros/imu/static_pressure', FluidPressure, self.pressure_cb)
        #rospy.Subscriber('/xsens/imu/data', Imu,  self.xsens_imu_cb)
        #rospy.Subscriber('/xsens/imu/')

        self.cycle()


    def state_cb(self, msg):
        self.state = msg

    def imu_cb(self, msg):
        self.imu = msg
        self.orientation['x'] = msg.orientation.x
        self.orientation['y'] = msg.orientation.y
        self.orientation['z'] = msg.orientation.z
        self.orientation['w'] = msg.orientation.w


    def imu_raw_cb(self, msg):
        self.imu_raw = msg
        self.angular_vel['x'] = msg.angular_velocity.x
        self.angular_vel['y'] = msg.angular_velocity.y
        self.angular_vel['z'] = msg.angular_velocity.z
        self.linear_accel['x'] = msg.linear_acceleration.x
        self.linear_accel['y'] = msg.linear_acceleration.y
        self.linear_accel['z'] = msg.linear_acceleration.z

    
    def mag_cb(self, msg):
        self.mag = msg
        self.mag_comp['x'] = msg.magnetic_field.x
        self.mag_comp['y'] = msg.magnetic_field.y
        self.mag_comp['z'] = msg.magnetic_field.z


    def pressure_cb(self, msg):
        self.pressure = msg
        self.fluid_pressure = msg.fluid_pressure


    def logger(self, i):
        
        row = list()
        row.append(i)
        row.append(rospy.get_time())
          
        components = [self.linear_accel,self.angular_vel,self.orientation,self.mag_comp]

        for di in components:
            for val in di.values():
                row.append(val)
        row.append(self.fluid_pressure)

        full_row = row

        if i < self.windows[0]:
            self.sw_rows_10.append(row[2:-1])
            full_row = full_row + 3*row[2:-1]
        else:
            self.sw_rows_10.pop(0)
            self.sw_rows_10.append(row[2:-1])
            sw = self.generate_sw(self.sw_rows_10,self.windows[0])
            full_row = full_row + sw
        
        if i < self.windows[1]:
            
            self.sw_rows_25.append(row[2:-1])
            full_row = full_row + 3*row[2:-1]
        else:
            self.sw_rows_25.pop(0)
            self.sw_rows_25.append(row[2:-1])
            sw = self.generate_sw(self.sw_rows_25,self.windows[1])
            full_row = full_row + sw
        
        if i < self.windows[2]:
            self.sw_rows_50.append(row[2:-1])
            full_row = full_row + 3*row[2:-1]
        else:
            self.sw_rows_50.pop(0)
            self.sw_rows_50.append(row[2:-1])
            sw = self.generate_sw(self.sw_rows_50,self.windows[2])
            full_row = full_row + sw
        
        with open (self.csv_out, 'a') as f:
            writer = csv.writer(f)
            writer.writerow(full_row)
        full_row.clear()


    def generate_sw(self, rows, window_length):

        data = pd.DataFrame(rows,columns = self.point_types[2:-1])
        sw = []
        for att in data.columns:
            col = data[att]
            sw = sw + [col.mean(), col.std(), col.mad()]
        return sw


    def cycle(self):
        iter = 0 
        rate = rospy.Rate(50.0)
        rospy.loginfo('CYCLING')
        while not rospy.is_shutdown():

            if self.state.mode == 'OFFBOARD':
                self.logger(iter)
                iter += 1
                rate.sleep()
            elif self.state.mode == 'AUTO.LAND':
                rospy.loginfo('BREAKING')
                break
            else:
                rate.sleep()

        # TODO
        # xsense integration
        # sliding windows


if __name__ == '__main__':
    rospy.init_node('data_logger', anonymous = True)
    dl = DataLogger()
    #dl.cycle()
