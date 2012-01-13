# phpMyAdmin MySQL-Dump
# http://phpwizard.net/phpMyAdmin/
#
# Host: localhost Database : nagios

# --------------------------------------------------------
#
# Table structure for table 'hostcomments'
#

CREATE TABLE hostcomments (
   hostcomment_id int(11) NOT NULL auto_increment,
   host_name varchar(75) NOT NULL,
   entry_time datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   persistent tinyint(4) DEFAULT '0' NOT NULL,
   author_name varchar(75) NOT NULL,
   comment_data blob NOT NULL,
   PRIMARY KEY (hostcomment_id)
);


# --------------------------------------------------------
#
# Table structure for table 'hostdowntime'
#

CREATE TABLE hostdowntime (
   hostdowntime_id int(11) NOT NULL auto_increment,
   host_name varchar(75) NOT NULL,
   entry_time datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   start_time datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   end_time datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   fixed tinyint(4) DEFAULT '0' NOT NULL,
   duration bigint(20) DEFAULT '0' NOT NULL,
   author_name varchar(75) NOT NULL,
   comment_data blob NOT NULL,
   PRIMARY KEY (hostdowntime_id)
);


# --------------------------------------------------------
#
# Table structure for table 'hostextinfo'
#

CREATE TABLE hostextinfo (
   host_name varchar(75) NOT NULL,
   notes_url varchar(128) NOT NULL,
   icon_image varchar(32) NOT NULL,
   vrml_image varchar(32) NOT NULL,
   gd2_icon_image varchar(32) NOT NULL,
   icon_image_alt varchar(128) NOT NULL,
   x_2d int(11) DEFAULT '-1' NOT NULL,
   y_2d int(11) DEFAULT '-1' NOT NULL,
   x_3d double(16,4) DEFAULT '-1.0000' NOT NULL,
   y_3d double(16,4) DEFAULT '-1.0000' NOT NULL,
   z_3d double(16,4) DEFAULT '-1.0000' NOT NULL,
   have_2d_coords tinyint(4) DEFAULT '0' NOT NULL,
   have_3d_coords tinyint(4) DEFAULT '0' NOT NULL
);


# --------------------------------------------------------
#
# Table structure for table 'hostretention'
#

CREATE TABLE hostretention (
   host_name varchar(75) NOT NULL,
   host_state tinyint(4) DEFAULT '0' NOT NULL,
   last_check int(11) DEFAULT '0' NOT NULL,
   checks_enabled tinyint(4) DEFAULT '0' NOT NULL,
   time_up int(11) DEFAULT '0' NOT NULL,
   time_down int(11) DEFAULT '0' NOT NULL,
   time_unreachable int(11) DEFAULT '0' NOT NULL,
   last_notification int(11) DEFAULT '0' NOT NULL,
   current_notification int(11) DEFAULT '0' NOT NULL,
   notifications_enabled tinyint(4) DEFAULT '0' NOT NULL,
   event_handler_enabled tinyint(4) DEFAULT '0' NOT NULL,
   problem_has_been_acknowledged tinyint(4) DEFAULT '0' NOT NULL,
   plugin_output blob NOT NULL,
   flap_detection_enabled tinyint(4) DEFAULT '0' NOT NULL,
   failure_prediction_enabled tinyint(4) DEFAULT '0' NOT NULL,
   process_performance_data tinyint(4) DEFAULT '0' NOT NULL,
   last_state_change int(11) DEFAULT '0' NOT NULL
);


# --------------------------------------------------------
#
# Table structure for table 'hoststatus'
#

CREATE TABLE hoststatus (
   host_name varchar(75) NOT NULL,
   host_status varchar(16) NOT NULL,
   last_update datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   last_check datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   last_state_change datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   problem_acknowledged tinyint(4) DEFAULT '0' NOT NULL,
   time_up int(11) DEFAULT '0' NOT NULL,
   time_down int(11) DEFAULT '0' NOT NULL,
   time_unreachable int(11) DEFAULT '0' NOT NULL,
   last_notification datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   current_notification int(11) DEFAULT '0' NOT NULL,
   notifications_enabled tinyint(4) DEFAULT '0' NOT NULL,
   event_handler_enabled tinyint(4) DEFAULT '0' NOT NULL,
   checks_enabled tinyint(4) DEFAULT '0' NOT NULL,
   plugin_output blob,
   flap_detection_enabled tinyint(4) DEFAULT '0' NOT NULL,
   is_flapping tinyint(4) DEFAULT '0' NOT NULL,
   percent_state_change float(10,2) DEFAULT '0.00' NOT NULL,
   scheduled_downtime_depth int(11) DEFAULT '0' NOT NULL,
   failure_prediction_enabled tinyint(4) DEFAULT '0' NOT NULL,
   process_performance_data tinyint(4) DEFAULT '0' NOT NULL
);


# --------------------------------------------------------
#
# Table structure for table 'programretention'
#

CREATE TABLE programretention (
   execute_service_checks tinyint(4) DEFAULT '0' NOT NULL,
   accept_passive_checks tinyint(4) DEFAULT '0' NOT NULL,
   enable_event_handlers tinyint(4) DEFAULT '0' NOT NULL,
   obsess_over_services tinyint(4) DEFAULT '0' NOT NULL,
   enable_flap_detection tinyint(4) DEFAULT '0' NOT NULL,
   enable_notifications tinyint(4) DEFAULT '0' NOT NULL,
   enable_failure_prediction tinyint(4) DEFAULT '0' NOT NULL,
   process_performance_data tinyint(4) DEFAULT '0' NOT NULL
);


# --------------------------------------------------------
#
# Table structure for table 'programstatus'
#

CREATE TABLE programstatus (
   last_update datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   program_start datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   daemon_mode tinyint(4) DEFAULT '0' NOT NULL,
   nagios_pid int(11) DEFAULT '0' NOT NULL,
   last_command_check datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   last_log_rotation datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   execute_service_checks tinyint(4) DEFAULT '0' NOT NULL,
   accept_passive_service_checks tinyint(4) DEFAULT '0' NOT NULL,
   enable_event_handlers tinyint(4) DEFAULT '0' NOT NULL,
   obsess_over_services tinyint(4) DEFAULT '0' NOT NULL,
   enable_flap_detection tinyint(4) DEFAULT '0' NOT NULL,
   enable_notifications tinyint(4) DEFAULT '0' NOT NULL,
   enable_failure_prediction tinyint(4) DEFAULT '0' NOT NULL,
   process_performance_data tinyint(4) DEFAULT '0' NOT NULL
);


# --------------------------------------------------------
#
# Table structure for table 'servicecomments'
#

CREATE TABLE servicecomments (
   servicecomment_id int(11) NOT NULL auto_increment,
   host_name varchar(75) NOT NULL,
   service_description varchar(128) NOT NULL,
   persistent tinyint(4) DEFAULT '0' NOT NULL,
   entry_time datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   author_name varchar(75) NOT NULL,
   comment_data blob NOT NULL,
   PRIMARY KEY (servicecomment_id)
);


# --------------------------------------------------------
#
# Table structure for table 'servicedowntime'
#

CREATE TABLE servicedowntime (
   servicedowntime_id int(11) NOT NULL auto_increment,
   host_name varchar(75) NOT NULL,
   service_description varchar(128) NOT NULL,
   entry_time datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   start_time datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   end_time datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   fixed tinyint(4) DEFAULT '0' NOT NULL,
   duration bigint(20) DEFAULT '0' NOT NULL,
   author_name varchar(75) NOT NULL,
   comment_data blob NOT NULL,
   PRIMARY KEY (servicedowntime_id)
);


# --------------------------------------------------------
#
# Table structure for table 'serviceextinfo'
#

CREATE TABLE serviceextinfo (
   host_name varchar(75) NOT NULL,
   service_description varchar(128) NOT NULL,
   notes_url varchar(128) NOT NULL,
   icon_image varchar(32) NOT NULL,
   icon_image_alt varchar(128) NOT NULL
);


# --------------------------------------------------------
#
# Table structure for table 'serviceretention'
#

CREATE TABLE serviceretention (
   host_name varchar(75) NOT NULL,
   service_description varchar(128) NOT NULL,
   service_state tinyint(4) DEFAULT '0' NOT NULL,
   last_check int(11) DEFAULT '0' NOT NULL,
   check_type tinyint(4) DEFAULT '0' NOT NULL,
   time_ok int(11) DEFAULT '0' NOT NULL,
   time_warning int(11) DEFAULT '0' NOT NULL,
   time_unknown int(11) DEFAULT '0' NOT NULL,
   time_critical int(11) DEFAULT '0' NOT NULL,
   last_notification int(11) DEFAULT '0' NOT NULL,
   current_notification int(11) DEFAULT '0' NOT NULL,
   notifications_enabled tinyint(4) DEFAULT '0' NOT NULL,
   checks_enabled tinyint(4) DEFAULT '0' NOT NULL,
   accept_passive_checks tinyint(4) DEFAULT '0' NOT NULL,
   event_handler_enabled tinyint(4) DEFAULT '0' NOT NULL,
   problem_has_been_acknowledged tinyint(4) DEFAULT '0' NOT NULL,
   plugin_output blob NOT NULL,
   flap_detection_enabled tinyint(4) DEFAULT '0' NOT NULL,
   failure_prediction_enabled tinyint(4) DEFAULT '0' NOT NULL,
   process_performance_data tinyint(4) DEFAULT '0' NOT NULL,
   obsess_over_service tinyint(4) DEFAULT '0' NOT NULL,
   last_state_change int(11) DEFAULT '0' NOT NULL
);


# --------------------------------------------------------
#
# Table structure for table 'servicestatus'
#

CREATE TABLE servicestatus (
   host_name varchar(75) NOT NULL,
   service_description varchar(128) NOT NULL,
   service_status varchar(16) NOT NULL,
   last_update datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   current_attempt int(11) DEFAULT '0' NOT NULL,
   max_attempts int(11) DEFAULT '0' NOT NULL,
   state_type varchar(5) DEFAULT '0' NOT NULL,
   last_check datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   next_check datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   should_be_scheduled tinyint(4) DEFAULT '0' NOT NULL,
   check_type varchar(8) DEFAULT '0' NOT NULL,
   checks_enabled tinyint(4) DEFAULT '0' NOT NULL,
   accept_passive_checks tinyint(4) DEFAULT '0' NOT NULL,
   event_handler_enabled tinyint(4) DEFAULT '0' NOT NULL,
   last_state_change datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   problem_acknowledged tinyint(4) DEFAULT '0' NOT NULL,
   last_hard_state varchar(16) NOT NULL,
   time_ok int(11) DEFAULT '0' NOT NULL,
   time_warning int(11) DEFAULT '0' NOT NULL,
   time_unknown int(11) DEFAULT '0' NOT NULL,
   time_critical int(11) DEFAULT '0' NOT NULL,
   last_notification datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
   current_notification int(11) DEFAULT '0' NOT NULL,
   notifications_enabled tinyint(4) DEFAULT '0' NOT NULL,
   latency int(11) DEFAULT '0' NOT NULL,
   execution_time int(11) DEFAULT '0' NOT NULL,
   plugin_output blob NOT NULL,
   flap_detection_enabled tinyint(4) DEFAULT '0' NOT NULL,
   is_flapping tinyint(4) DEFAULT '0' NOT NULL,
   percent_state_change float(10,2) DEFAULT '0.00' NOT NULL,
   scheduled_downtime_depth int(11) DEFAULT '0' NOT NULL,
   failure_prediction_enabled tinyint(4) DEFAULT '0' NOT NULL,
   process_performance_data tinyint(4) DEFAULT '0' NOT NULL,
   obsess_over_service tinyint(4) DEFAULT '0' NOT NULL
);
