# 该脚本用来获取scene组信息，并产生一个列表

with open('../sc.txt', encoding='utf-8') as sc:
    data = sc.read()
    groups = data.split('•')
    scene_groups = []
    for group in groups:
        if group == '':
            continue
        scene_groups.append(group.strip())
    print(scene_groups)
