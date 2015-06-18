from django.shortcuts import render_to_response
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../..")

import forms
from common import task
from common import const

def index(request):
    return render_to_response('index.html')

def search_task(request):
    if request.method == 'POST':
        form = forms.TaskSearchForm(request.POST)
        if form.is_valid():
            current_page = str_to_int(form.cleaned_data['current_page'])
            task_id = str_to_int(form.cleaned_data['task_id'].strip())
            t = task.Task(task_id = task_id, 
                          type = form.cleaned_data['type'], 
                          status = form.cleaned_data['status'])
        else:
            current_page = 1
            t = task.Task(task_id = None, type = const.T_ALL, status = const.T_ALL)
    else:
        form = forms.TaskSearchForm()
        current_page = 1
        t = task.Task(task_id = None, type = const.T_ALL, status = const.T_ALL)
    task_list, total_page = t.search(current_page)
    form_data = form.data.copy()
    form_data['total_page'] = total_page
    form_data['current_page'] = current_page
    form = forms.TaskSearchForm(form_data)
    return render_to_response('tasklist.html', {'form': form, 'task_list': task_list})

def create_task(request):
    success = 'init'
    if request.method == 'POST':
        form = forms.TaskForm(request.POST)
        if form.is_valid():
            type = form.cleaned_data['type'].strip()
            if type == const.T_IP_SCAN:
                t = task.IpTask(type = form.cleaned_data['type'].strip(),
                                status = const.T_SUBMITTED,
                                ip = form.cleaned_data['ip'].strip(),
                                seq_ran = form.cleaned_data['seq_ran'].strip())
            elif type == const.T_IP_BLOCK_SCAN:
                t = task.IpBlockTask(type = form.cleaned_data['type'].strip(),
                                     status = const.T_SUBMITTED,
                                     ip = form.cleaned_data['ip_begin'].strip(),
                                     ip_end = form.cleaned_data['ip_end'].strip(),
                                     seq_ran = form.cleaned_data['seq_ran'].strip())
            else:
                t = task.PortTask(type = form.cleaned_data['type'].strip(),
                                  status = const.T_SUBMITTED,
                                  ip = form.cleaned_data['ip'].strip(),
                                  port_begin = int(form.cleaned_data['port_begin'].strip()),
                                  port_end = int(form.cleaned_data['port_end'].strip()),
                                  seq_ran = form.cleaned_data['seq_ran'].strip())
            success = t.insert()
            form = forms.TaskForm()
        else:
            #print form.errors.items()[0][1][0]
            success = json.dumps(form.errors)
    else:
        form = forms.TaskForm()
    return render_to_response('createtask.html', {'form': form, 'success': success})

def open_task(request):
    taskid = int(request.GET.get('task_id'))
    type = request.GET.get('type')
    if type == const.T_IP_SCAN:
        t = task.IpTask(task_id = taskid)
    elif type == const.T_IP_BLOCK_SCAN:
        t = task.IpBlockTask(task_id = taskid)
    else:
        t = task.PortTask(task_id = taskid)
    t.get_task()
    form = get_form_from_task(t)
    return render_to_response('opentask.html', {'form': form})

def task_jobs(request):
    taskid = int(request.GET.get('task_id'))
    type = request.GET.get('type')
    current_page = int(request.GET.get('current_page'))
    if type == const.T_IP_SCAN:
        t = task.IpTask(task_id = taskid)
    elif type == const.T_IP_BLOCK_SCAN:
        t = task.IpBlockTask(task_id = taskid)
    else:
        t = task.PortTask(task_id = taskid)
    job_list, total_page = t.get_job_list(current_page)
    return render_to_response('taskjobs.html', {'job_list': job_list, 'task_id': taskid, 'type': type, \
                                                'current_page': current_page, 'total_page': total_page})

def task_reports(request):
    taskid = int(request.GET.get('task_id'))
    type = request.GET.get('type')
    current_page = int(request.GET.get('current_page'))
    if type == const.T_IP_SCAN:
        t = task.IpTask(task_id = taskid)
    elif type == const.T_IP_BLOCK_SCAN:
        t = task.IpBlockTask(task_id = taskid)
    else:
        t = task.PortTask(task_id = taskid)
    report_list, total_page = t.get_report_list(current_page)
    return render_to_response('taskreports.html', {'report_list': report_list, 'task_id': taskid, 'type': type, \
                                                'current_page': current_page, 'total_page': total_page})

def check_scanner(request):
    current_page = int(request.GET.get('current_page'))
    scanner_list, total_page = task.get_scanner_list(current_page)
    running_scanner_list, running_num = task.get_running_scanner_performance()
    return render_to_response('checkscanner.html', {'scanner_list': scanner_list, 'running_scanner_list': running_scanner_list,
                                                    'running_num': running_num, 'current_page': current_page, 'total_page': total_page})

def str_to_int(str):
    if str is None or str == "":
        return None
    try:
        return int(str)
    except ValueError:
        return 0

def get_form_from_task(task):
    form = forms.TaskViewForm()
    form.fields['task_id'].initial = task.task_id
    form.fields['type'].initial = task.type
    form.fields['status'].initial = task.status
    form.fields['seq_ran'].initial = task.seq_ran
    form.fields['submit_time'].initial = task.submit_time
    form.fields['finish_time'].initial = task.finish_time
    if task.type == const.T_IP_SCAN:
        form.fields['ip'].initial = task.ip
    elif task.type == const.T_IP_BLOCK_SCAN:
        form.fields['ip_begin'].initial = task.ip
        form.fields['ip_end'].initial = task.ip_end
    else: 
        form.fields['ip'].initial = task.ip
        form.fields['port_begin'].initial = task.port_begin
        form.fields['port_end'].initial = task.port_end
    return form
