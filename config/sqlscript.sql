DROP DATABASE IF EXISTS portscanner;
CREATE DATABASE portscanner;
USE portscanner;

CREATE TABLE `scanner` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ip` varchar(15) NOT NULL,
  `port` int(11) NOT NULL,
  `status` enum('RUNNING','STOPPED') NOT NULL,
  `update_time` timestamp(1) NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=40 DEFAULT CHARSET=latin1;

CREATE TABLE `task` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` enum('IP_SCAN','IP_BLOCK_SCAN','NORMAL_SCAN','SYN_SCAN','FIN_SCAN') NOT NULL,
  `status` enum('SUBMITTED','RUNNING','FINISHED') NOT NULL,
  `ip` varchar(15) DEFAULT NULL,
  `ip_end` varchar(15) DEFAULT NULL,
  `port_begin` int(11) DEFAULT NULL,
  `port_end` int(11) DEFAULT NULL,
  `seq_ran` enum('SEQ','RAN') DEFAULT NULL,
  `submit_time` timestamp(1) NULL DEFAULT NULL,
  `finish_time` timestamp(1) NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=56 DEFAULT CHARSET=latin1;

CREATE TABLE `job` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `task_id` int(11) NOT NULL,
  `scanner_id` int(11) DEFAULT NULL,
  `type` enum('IP_SCAN','IP_BLOCK_SCAN','NORMAL_SCAN','SYN_SCAN','FIN_SCAN') DEFAULT NULL,
  `status` enum('RUNNING','FINISHED') DEFAULT NULL,
  `ip` varchar(15) DEFAULT NULL,
  `ip_end` varchar(15) DEFAULT NULL,
  `port_begin` int(11) DEFAULT NULL,
  `port_end` int(11) DEFAULT NULL,
  `seq_ran` enum('SEQ','RAN') DEFAULT NULL,
  `num` int(11) DEFAULT NULL,
  `assign_time` timestamp(1) NULL DEFAULT NULL,
  `finish_time` timestamp(1) NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=137 DEFAULT CHARSET=latin1;

CREATE TABLE `report` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `task_id` int(11) NOT NULL,
  `job_id` int(11) NOT NULL,
  `ip` varchar(15) DEFAULT NULL,
  `port` int(11) DEFAULT NULL,
  `res` enum('ON','OFF','FILTER') DEFAULT NULL,
  `banner` text,
  `update_time` timestamp(1) NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=43230 DEFAULT CHARSET=latin1;












