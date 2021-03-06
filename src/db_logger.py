#!/usr/bin/env python
"""
Author: Jason Hughes
Date: June 2022
Log IMU data from pixhawk and xsens to sqlite db
"""

import sqlite3
import rospy
import copy
import os
import pandas as pd
from datetime import datetime
from sensor_msgs.msg import Imu, MagneticField, FluidPressure
from mavros_msgs.msg import State
from geometry_msgs.msg import Vector3Stamped, PoseStamped
from tf.transformations import euler_from_quaternion, quaternion_from_euler

class DataBaseLogger():

    def __init__(self):
        dt = datetime.now()
        time_str = str(dt.month) +'_'+ str(dt.day)+'_'+str(dt.year)+'_'+str(dt.hour)+'_'+str(dt.minute)+'_'+str(dt.second)
        self.system_name = os.getlogin()
        self.db_name = 'collection_'+time_str
        self.db_out = rospy.get_param('/logger/logger_path') + 'collection_'+time_str+'.db'
        self.use_xsens = rospy.get_param('/external/use')
        
        self.windows = rospy.get_param('/logger/windows')

        if self.use_xsens:
            self.data_points = rospy.get_param('/logger/point_types')+rospy.get_param('/external/point_types')
        else:
            self.data_points = rospy.get_param('/logger/point_types')
        name = rospy.get_param('/logger/name')      
        self.attributes = copy.copy(self.data_points)

        self.generate_columns()
        self.state = State()
        self.orientation = [] 
        self.angular_vel = [] 
        self.linear_accel = [] 
        self.mag_comp = [] 
        self.external_orientation = []
        self.external_angular_vel = []
        self.external_linear_accel = []
        self.external_accel = []
        self.external_mag = []
        self.fluid_pressure = 0.0
        self.rpy = []
        self.external_rpy = []
        self.pose = []

        self.data = pd.DataFrame(columns = self.attributes)
        
        rospy.Subscriber('/mavros/state', State, self.state_cb)
        rospy.Subscriber('/mavros/imu/data', Imu, self.imu_cb)
        rospy.Subscriber('/mavros/imu/data_raw', Imu, self.imu_raw_cb)
        rospy.Subscriber('/mavros/imu/mag', MagneticField, self.mag_cb)
        rospy.Subscriber('/mavros/imu/static_pressure', FluidPressure, self.pressure_cb)
        rospy.Subscriber('/imu/data', Imu,  self.external_imu_cb)
        rospy.Subscriber('/mag', MagneticField, self.external_mag_cb)
        rospy.Subscriber('/vrpn_client_node/'+name+'/pose', PoseStamped, self.pose_cb)
        
        self.cycle()

    def generate_columns(self):
        for win in self.windows:
            for att in self.data_points[5:]:
                self.attributes.append(str(att)+'_sw_mean_'+str(win))
                self.attributes.append(str(att)+'_sw_std_'+str(win))
                self.attributes.append(str(att)+'_sw_mad_'+str(win))
        print("num attributes: ", len(self.attributes))

    def generate_str(self):
        write_str = "CREATE TABLE IF NOT EXISTS "+self.db_name+" (id INTEGER PRIMARTY KEY, ros_time FLOAT, "
        for i in range(2,len(self.attributes)):
            if i == len(self.attributes)-1:
                write_str = write_str + self.attributes[i] + " FLOAT)"
            else:
                write_str = write_str + self.attributes[i] +" FLOAT, "
        return write_str

    def generate_sw(self, start, stop):
        d = self.data.iloc[start:stop]
        avgs = []
        for att in self.data_points[5:]:
            col = d[att]
            avgs = avgs + [col.mean(), col.std(), col.mad()]
        return avgs
        
        
    def write(self):
        self.data.to_csv('/home/'+self.system_name'/arch_ws/src/dlio_logger/data/test.csv', index=False)
        conn = sqlite3.connect(self.db_out)
        cur = conn.cursor()
        
        cur.execute(self.generate_str())

        self.data.to_sql(self.db_name, conn, if_exists='replace', index=False)
        
    def state_cb(self, msg):
        self.state = msg

    def pose_cb(self, msg):
        self.pose = [msg.pose.position.x, msg.pose.position.y, msg.pose.position.z]
        
    def external_mag_cb(self, msg):
        self.external_mag = [msg.magnetic_field.x, msg.magnetic_field.y, msg.magnetic_field.z]
        
    def external_imu_cb(self, msg):
        self.external_orientation = [msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w]
        self.external_angular_vel = [msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z]
        self.external_linear_accel = [msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z]
        self.external_rpy = list(euler_from_quaternion(self.external_orientation)) 

    def imu_cb(self, msg):
        self.imu = msg
        self.orientation = [msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w]
        self.rpy = list(euler_from_quaternion(self.orientation))


    def imu_raw_cb(self, msg):
        self.imu_raw = msg
        self.angular_vel = [msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z]
        self.linear_accel = [msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z]

    
    def mag_cb(self, msg):
        self.mag = msg
        self.mag_comp = [msg.magnetic_field.x, msg.magnetic_field.y, msg.magnetic_field.z]


    def pressure_cb(self, msg):
        self.pressure = msg
        self.fluid_pressure = msg.fluid_pressure

    def log(self, i):
        
        if self.use_xsens:
            row =([i]
                  +[rospy.get_time()]
                  +self.pose
                  +self.linear_accel
                  +self.angular_vel
                  +self.orientation
                  +self.mag_comp
                  +[self.fluid_pressure]
                  +self.rpy
                  +self.external_linear_accel
                  +self.external_angular_vel
                  +self.external_orientation
                  +self.external_mag
                  +self.external_rpy)
        else:
            row = ([i]
                   +[rospy.get_time()]
                   +self.pose
                   +self.linear_accel
                   +self.angular_vel
                   +self.orientation
                   +self.mag_comp
                   +[self.fluid_pressure])

        if i < self.windows[0]:
            sw_row_1 = self.generate_sw(0,i)
            sw_row_2 = self.generate_sw(0,i)
            sw_row_3 = self.generate_sw(0,i)
            self.data.loc[i] = row+sw_row_1+sw_row_2+sw_row_3
        elif i < self.windows[1]:
            sw_row_1 = self.generate_sw(i-self.windows[0],i)
            sw_row_2 = self.generate_sw(0,i)
            sw_row_3 = self.generate_sw(0,i)
            self.data.loc[i] = row+sw_row_1+sw_row_2+sw_row_3
        elif i < self.windows[2]:
            sw_row_1 = self.generate_sw(i-self.windows[0],i)
            sw_row_2 = self.generate_sw(i-self.windows[1],i)
            sw_row_3 = self.generate_sw(0,i) 
            self.data.loc[i] = row+sw_row_1+sw_row_2+sw_row_3
        else:
            sw_row_1 = self.generate_sw(i-self.windows[0],i)
            sw_row_2 = self.generate_sw(i-self.windows[1],i)
            sw_row_3 = self.generate_sw(i-self.windows[2],i)
            self.data.loc[i] = row+sw_row_1+sw_row_2+sw_row_3
        
            
    def cycle(self):
        iter = 0 
        rate = rospy.Rate(rospy.get_param('/logger/sample_rate'))
        j = 0
        rospy.loginfo('waiting for data...')
        while j < 100:
            
            j += 1
            rate.sleep()
            
        rospy.loginfo("CYCLING")
        while not rospy.is_shutdown():
            
            if self.state.mode == 'OFFBOARD':
                self.log(iter)
                iter += 1
                rate.sleep()
            elif self.state.mode == 'AUTO.LAND':
                self.write()
                rospy.loginfo('BREAKING')
                break
            else:
                rate.sleep()


if __name__ == '__main__':
    rospy.init_node('database_logger', anonymous = True)
    DataBaseLogger()
