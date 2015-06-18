from django import forms
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../..")

from common import const

_STATUS_CHOICES = (
    (const.T_ALL, ""),
    (const.T_SUBMITTED, const.T_SUBMITTED),
    (const.T_RUNNING, const.T_RUNNING),
    (const.T_FINISHED, const.T_FINISHED),
)

_TYPE_CHOICES = (
    (const.T_ALL, ""),
    (const.T_IP_SCAN, const.T_IP_SCAN),
    (const.T_IP_BLOCK_SCAN, const.T_IP_BLOCK_SCAN),
    (const.T_PORT_SCAN, const.T_PORT_SCAN),
    (const.T_SYN_SCAN, const.T_SYN_SCAN),
    (const.T_FIN_SCAN, const.T_FIN_SCAN),
)

_TYPE_CHOICES_NO_NULL = (
    (const.T_IP_SCAN, const.T_IP_SCAN),
    (const.T_IP_BLOCK_SCAN, const.T_IP_BLOCK_SCAN),
    (const.T_PORT_SCAN, const.T_PORT_SCAN),
    (const.T_SYN_SCAN, const.T_SYN_SCAN),
    (const.T_FIN_SCAN, const.T_FIN_SCAN),
)

_SEQ_RAN_CHOICES = (
    (const.SCAN_SEQ, const.SCAN_SEQ),
    (const.SCAN_RAN, const.SCAN_RAN),
)

class TaskSearchForm(forms.Form):
    task_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm"}))
    type = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class' : 'form-control input-sm'}), choices = _TYPE_CHOICES)
    status = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class' : 'form-control input-sm'}), choices = _STATUS_CHOICES)
    current_page = forms.IntegerField(required=False, widget=forms.HiddenInput())
    total_page = forms.IntegerField(required=False, widget=forms.HiddenInput())


class TaskForm(forms.Form):
    type = forms.ChoiceField(required=True, widget=forms.Select(attrs={'class' : 'form-control input-sm', 'onchange': 'javascript:type_change()'}), 
                             choices = _TYPE_CHOICES_NO_NULL)
    ip = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm"}))
    ip_begin = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm"}))
    ip_end = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm"}))
    port_begin = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm"}))
    port_end = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm"}))
    seq_ran = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class' : 'form-control input-sm'}), choices = _SEQ_RAN_CHOICES)

    def clean(self):
        cleaned_data = super(TaskForm, self).clean()
        task_type = cleaned_data.get("type")
        if task_type == const.T_IP_SCAN:
            ip = cleaned_data.get("ip").strip()
            if ip is None or len(ip) == 0:
                raise forms.ValidationError('Please fill in the ip address')
            if not check_valid_ipv4(ip):
                raise forms.ValidationError('Invalid ip address')
        elif task_type == const.T_IP_BLOCK_SCAN:
            ip_begin = cleaned_data.get("ip_begin").strip()
            if ip_begin is None or len(ip_begin) == 0:
                raise forms.ValidationError('Please fill in the start ip address')
            if not check_valid_ipv4(ip_begin):
                raise forms.ValidationError('Invalid start ip address')
            ip_end = cleaned_data.get("ip_end").strip()
            if ip_end is None or len(ip_end) == 0:
                raise forms.ValidationError('Please fill in the end ip address')
            if not check_valid_ipv4(ip_end):
                raise forms.ValidationError('Invalid end ip address')
            r, msg = check_ip_begin_end(ip_begin, ip_end)
            if not r:
                raise forms.ValidationError(msg)
        else:
            ip = cleaned_data.get("ip").strip()
            if ip is None or len(ip) == 0:
                raise forms.ValidationError('Please fill in the ip address')
            if not check_valid_ipv4(ip):
                raise forms.ValidationError('Invalid ip address')
            port_begin = cleaned_data.get("port_begin").strip()
            if port_begin is None or len(port_begin) == 0:
                raise forms.ValidationError('Please fill in the start port')
            if not check_port(port_begin):
                raise forms.ValidationError('Invalid start port number')
            port_end = cleaned_data.get("port_end").strip()
            if port_end is None or len(port_end) == 0:
                raise forms.ValidationError('Please fill in the end port')
            if not check_port(port_end):
                raise forms.ValidationError('Invalid end port number')
            if int(port_begin) > int(port_end):
                raise forms.ValidationError('Start ip should be smaller than or equal to end ip')
        return cleaned_data


class TaskViewForm(forms.Form):
    task_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))
    type = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))
    status = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))
    ip = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))
    ip_begin = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))
    ip_end = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))
    port_begin = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))
    port_end = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))
    seq_ran = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))
    submit_time = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))
    finish_time = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': "form-control input-sm", 'readonly': "readonly"}))


def check_valid_ipv4(ip):
    blocks = ip.split('.')
    if len(blocks) != 4:
        return False
    for block in blocks:
        if not block.isdigit():
            return False
        block_int = int(block)
        if  block_int < 0 or  block_int > 255:
            return False
    return True    

def check_ip_begin_end(ip_begin, ip_end):
    blocks_begin = ip_begin.split('.')
    blocks_end = ip_end.split('.')
    if blocks_begin[0] != blocks_end[0] or blocks_begin[1] != blocks_end[1] or blocks_begin[2] != blocks_end[2]:
        return False, 'Start ip and end ip are only allowed to be different in the last byte'
    if int(blocks_begin[3]) > int(blocks_end[3]):
        return False, 'Start ip should be smaller than or equal to end ip'
    return True, ''

def check_port(port):
    if not port.isdigit():
        return False
    if int(port) <= 0 or int(port) > 65535:
        return False
    return True  
