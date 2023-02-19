# 该脚本用来更新支持平台
import site_api
a = ''
with open('../platforms.txt', 'w') as p:
    for i in site_api.platform_dict:
        a += '{}\n'.format(i)
    p.write(a)
