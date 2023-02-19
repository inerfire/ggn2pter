import requests
import re
from bs4 import BeautifulSoup
import os
import happyfunc
import json
import bencodepy
import constant
from html2phpbbcode.parser import HTML2PHPBBCode

PTER_KEY = constant.pter_key
ANONYMOUS = constant.anonymous
TORRENT_DIR = constant.torrent_dir
HEADERS = constant.headers
ELITEGAMER = constant.elite_gamer
IMGBBKEY = constant.imgbb_key
GGNAPI = constant.ggn_api


def true_input(content):
    while True:
        output = input(content)
        if output == '':
            print('输入内容不能为空！')
        else:
            return output


def upload_imgbb(img):
    api = 'https://api.imgbb.com/1/upload'
    data = {'key': IMGBBKEY, 'image': img}
    response = requests.post(url=api, data=data).json()
    if response['success']:
        img = response['data']['display_url']
    return img


def find_indie(game_name):
    api_url = 'https://indienova.com/get/gameDBName'
    num = 1
    params = {'query': game_name}
    data = {}
    res = requests.get(api_url, headers=HEADERS, params=params).json()
    for i in res:
        data[str(num)] = i
        num += 1
    return data


class GGnApi:
    def __init__(self, dl_link, cookies=None):
        self.session = requests.Session()
        self.session_cookies = cookies
        self.session.headers = HEADERS
        self.dl_link = dl_link
        self.torrent_id = re.search(r'id=(\d+)', dl_link).group(1)
        self.verified = 'no'

    def _install_cookies(self):
        if not self.session_cookies:
            with open('cookies.json', 'r') as r:
                cookies = json.load(r)
            cookies = happyfunc.cookie2dict(cookies['ggn'])
            self.session.cookies = requests.utils.cookiejar_from_dict(cookies)
        else:
            return None

    def _name_tweak(self):
        if 'GOG' in self.release_edition.upper():
            self.release_title += '-GOG'
            self.verified = 'yes'
        elif 'INTRO' in self.release_edition.upper():
            self.release_title += '-No-Intro'
            self.verified = 'yes'
        elif 'REDUMP' in self.release_edition.upper():
            self.release_title += '-redump.org'
            self.verified = 'yes'

    def _handle_api(self):
        url = 'https://gazellegames.net/api.php?request=torrent&id={}'.format(self.torrent_id)
        self.session.headers.update({'X-API-Key': GGNAPI})
        res = self.session.get(url).json()
        game_info = res['response']['group']
        self.name = game_info['name']
        self.platform = game_info['platform']
        links = game_info['gameInfo']['weblinks']
        self.steam = links['Steam'] if 'Steam' in links else None
        self.epic = links['EpicGames'] if 'EpicGames' in links else None
        torrent_info = res['response']['torrent']
        self.release_title = torrent_info['releaseTitle'].replace('/', '').replace('[FitGirl Repack]', '-Fitgirl')
        self.torrent_desc = torrent_info['bbDescription'].replace('[align=center]', '').replace('[/align]', '')
        self.release_edition = torrent_info['remasterTitle'] if torrent_info[
                                                                    'remastered'] is True else 'Original Edition'
        self.release_type = torrent_info['releaseType']
        self.release_type = torrent_info['gameDOXType'] if self.release_type == 'GameDOX' else self.release_type
        self.scene = 'yes' if torrent_info['scene'] is True else 'no'
        self.verified = 'yes' if self.release_type in 'P2P DRM Free' else 'no'
        self._name_tweak()

    def _find_store(self):
        url = 'https://gazellegames.net/torrents.php?torrentid={}'.format(self.torrent_id)
        url = self.session.get(url).url
        res = self.session.get(url)
        self.res_soup = BeautifulSoup(res.text, 'lxml')
        self.name = re.search(r'-\s(.+)\s\(\d{4}', self.res_soup.select_one('#display_name').text).group(1)
        try:
            self.steam = self.res_soup.select_one('a[href*="store.steampowered.com/app/"][title="Steam"]')[
                'href']
        except TypeError:
            self.steam = None
        try:
            self.epic = self.res_soup.select_one('a[href*="www.epicgames.com/store"][title="EpicGames"]')[
                'href']
        except TypeError:
            self.epic = None
        return {'steam': self.steam, 'epic': self.epic}

    def _get_desc(self):
        release_element = self.res_soup.select_one('a[onclick*="#torrent_{}"]'.format(self.torrent_id))
        parsed_title, release_tag = re.search(r'(.+) (\[.+])', release_element.text.strip()).groups()
        release_tag = [i.replace(']', '').strip() if '!' not in i else None for i in release_tag.split(',')]
        release_tag = list(filter(None, release_tag))

        if ELITEGAMER == 'yes':
            url = 'https://gazellegames.net/torrents.php?action=edit&id={}'.format(self.torrent_id)
            # url = 'http://127.0.0.1:85/ggn5.html'
            desc = self.session.get(url)
            desc_soup = BeautifulSoup(desc.text, 'lxml')
            self.torrent_desc = desc_soup.select_one('#release_desc').text.replace('[align=center]', '').replace(
                '[/align]', '')
            self.release_title = desc_soup.select_one('#release_title').get('value').replace('/',
                                                                                             '') if desc_soup.select_one(
                '#release_title').get('value') else self.name
            self.release_edition = desc_soup.select_one('#remaster_title').get('value').upper() if desc_soup.select_one(
                '#remaster_title') else 'Original Edition'
            self.release_type = desc_soup.select_one('#miscellaneous option[selected="selected"]').text
            if self.release_type == 'GameDOX':
                self.release_type = desc_soup.select_one('#gamedox option[selected="selected"]').text
            self.platform = desc_soup.select_one('#platform option[selected="selected"]').text
        else:
            self.release_edition = release_element.find_parent('tbody').find_previous_sibling().td.text
            self.release_title = parsed_title
            description_element = self.res_soup.select_one(
                'tr#torrent_{} blockquote#description'.format(self.torrent_id))
            torrent_description = HTML2PHPBBCode().feed(str(description_element)).replace('[list]', '').replace(
                '[/list]',
                '').replace(
                '[*]', '\n[*]')
            self.torrent_desc = re.sub(r'(/nfoimg/\d+\.png)', r'https://gazellegames.net\g<1>', torrent_description)
            self.release_type = release_tag[-1]
            if self.release_type == 'GameDOX':
                self.release_type = self.release_title.split('-')[-1].strip()
            self.platform = self.res_soup.select_one('#groupplatform a').text

        self.release_title = self.release_title.replace('/', '').replace('[FitGirl Repack]', '-Fitgirl')

        self._name_tweak()
        self.verified = 'yes' if self.release_type in 'P2P DRM Free' else self.verified
        self.scene = 'yes' if 'Scene' in release_tag else 'no'
        return self.torrent_desc

    def _download_torrent(self):
        res = self.session.get(self.dl_link)
        torrent = bytes()
        for chunk in res.iter_content(100000):
            torrent += chunk
        ggn_dir = os.path.join(TORRENT_DIR, 'ggn/')
        if not os.path.exists(ggn_dir):
            os.makedirs(ggn_dir)
        self.torrent_title = '{}-{}'.format(self.platform, re.sub(r'[/:*?"<>|]', '_', self.release_title))
        with open(os.path.join(ggn_dir, os.path.basename('[GGn]{}.torrent'.format(self.torrent_title))),
                  'wb') as t:
            t.write(torrent)
        torrent = bencodepy.decode(torrent)
        torrent[b'announce'] = b'https://tracker.pterclub.com/announce?passkey=' + bytes(PTER_KEY, encoding='utf-8')
        torrent[b'info'][b'source'] = bytes('[pterclub.com] ＰＴ之友俱乐部', encoding='utf-8')
        del torrent[b'comment']
        torrent = bencodepy.encode(torrent)
        with open(os.path.join('torrents', os.path.basename('[PTer]{}.torrent'.format(self.torrent_title))), 'wb') as t:
            t.write(torrent)

    def _return_terms(self):
        attr = {}
        for name, value in vars(self).items():
            attr[name] = value
        attr['res_soup'] = None
        attr['session'] = None
        return attr

    def worker(self):
        if GGNAPI:
            print('正在获取游戏&种子信息...')
            self._handle_api()
        else:
            self._install_cookies()
            print('正在获取游戏信息...')
            self._find_store()
            print('正在获取种子信息...')
            self._get_desc()
        print('正在下载种子...')
        self._download_torrent()
        return self._return_terms()


class PTerApi:
    def __init__(self, ggn_info, cookies=None):
        self.session = requests.Session()
        self.session_cookies = cookies
        self.session.headers = HEADERS
        self.name = ggn_info['name']
        self.platform = ggn_info['platform']
        self.steam = ggn_info['steam']
        self.epic = ggn_info['epic']
        self.release_title = ggn_info['release_title']
        self.torrent_title = ggn_info['torrent_title']
        self.release_type = ggn_info['release_type']
        self.torrent_desc = ggn_info['torrent_desc']
        self.scene = ggn_info['scene']
        self.verified = ggn_info['verified']
        self.gid = None
        self.uplver = ANONYMOUS

    def _install_cookies(self):
        if not self.session_cookies:
            with open('cookies.json', 'r') as r:
                cookies = json.load(r)
            cookies = happyfunc.cookie2dict(cookies['pter'])
            self.session.cookies = requests.utils.cookiejar_from_dict(cookies)
        else:
            return None

    def _find_game(self):
        print('将要上传的种子是：{}'.format(self.release_title))
        url = 'https://pterclub.com/searchgameinfo.php'
        params = {'name': self.name}
        # data = {'name':'into'}
        res = self.session.get(url, params=params)
        res_soup = BeautifulSoup(res.text, 'lxml')
        game_list = res_soup.select('a[title="点击发布这游戏设备的种子"]')
        platform_list = res_soup.select('img[src^="/pic/category/chd/scenetorrents/"]')
        if not game_list:
            return None
        game_dict = {}
        num = 1
        for game, platform in zip(game_list[::2], platform_list):
            gid = re.search(r'detailsgameinfo.php\?id=(\d+)', game['href']).group(1)
            game_dict[str(num)] = '{}: {} GID:{}'.format(platform['title'], game.text, gid)
            num += 1
        print('我们在猫站找到以下游戏，请选择要上传的游戏分组的编号(并非gid)，如果没有请输入0：')
        for num, game in game_dict.items():
            print('{}.{}'.format(num, game))
        gid = (true_input('编号： '))
        if gid == '0':
            return None
        print(game_dict[gid])
        gid = re.search(r'GID:(.+)', game_dict[gid]).group(1)
        print(gid)
        self.gid = gid
        return gid

    def _upload_game(self):
        url = 'https://pterclub.com/takeuploadgameinfo.php'
        if self.steam:
            game_info = happyfunc.steam_api(self.steam)
        # elif self.epic:
        #     game_info = happyfunc.epic_api(self.epic)
        else:
            print('未找到steam或epic链接，正在前往indenova查询\n... ... ...')
            indie_data = find_indie(self.name)
            for i in indie_data:
                print('{}.{}'.format(i, re.sub('http.+', '', indie_data[i]['title'])))
            indie_data = indie_data[input('请输入适配游戏的序号,没有请直接回车：')]['slug']
            if indie_data == '':
                return False
            game_info = happyfunc.indie_nova_api(indie_data)

        data = {'uplver': self.uplver, 'detailsgameinfoid': '0', 'name': self.name, 'color': '0', 'font': '0',
                'size': '0', 'descr': game_info['about'], 'console': constant.platform_dict[self.platform],
                'year': game_info['year'],
                'has_allowed_offer': '0',
                'small_descr': game_info['chinese_name'] if 'chinese_name' in game_info else input('请输入游戏中文名：')}
        game_url = self.session.post(url, data=data).url
        gid = re.search(r'detailsgameinfo.php\?id=(\d+)', game_url).group(1)
        self.gid = gid

    def _upload_torrent(self):
        if self.scene == 'yes':
            nfo_img = re.search(r'https?://gazellegames\.net/nfoimg/\d+\..+?g(?=\[/img])', self.torrent_desc).group(0)
            try:
                print('尝试上传nfo信息至图床....')
                new_nfo_img = upload_imgbb(nfo_img)
            except:
                print('上传nfo信息失败，将使用原始地址!')
                new_nfo_img = nfo_img
            self.torrent_desc = self.torrent_desc.replace(nfo_img, new_nfo_img)
        url = 'https://pterclub.com/takeuploadgame.php'
        torrent_file = os.path.join(TORRENT_DIR, '[PTer]{}.torrent'.format(self.torrent_title))
        file = ("file", (os.path.basename(torrent_file), open(torrent_file, 'rb'), 'application/x-bittorrent')),
        data = {'uplver': self.uplver, 'categories': constant.release_type_dict[self.release_type],
                'format': constant.release_format_dict[
                    self.release_type] if self.release_type in constant.release_format_dict else '7',
                'has_allowed_offer': '0', 'gid': self.gid,
                'descr': self.torrent_desc}
        region = true_input('请选择种子地区（直接输入数字即可）：\n1.大陆\n2.香港\n3.台湾\n4.英美\n5.韩国\n6.日本\n7.其它\n')
        if self.scene == 'yes':
            data['sce'] = self.scene
        if self.verified == 'yes':
            data['vs'] = self.verified
        if input('该资源是否有中文？（yes/no）默认为no：') == 'yes':
            data['zhongzi'] = 'yes'
        if input('该资源是否有国语？(yes/no) 默认为no：') == 'yes':
            data['guoyu'] = 'yes'
        data['team'] = region
        title_id = ''
        rom_format = ''
        if self.platform == "Switch":
            if self.scene != 'yes':
                title_id = '[{}]'.format(true_input('请输入NS游戏的title id：'))
            rom_format = '[{}]'.format(true_input('请输入NS游戏的格式:'))
        short_name = happyfunc.back0day(self.name, self.release_title) + title_id + rom_format
        print(self.release_title)
        user_title = input('智能检测到的种子标题为{}，若有错误，请输入正确的标题，没有请直接回车：'.format(short_name))
        user_title = short_name if user_title == '' else user_title
        data['name'] = user_title
        print('正在上传... ...')
        res = self.session.post(url, data=data, files=file, allow_redirects=False)
        if res.status_code != 302:
            res.encoding = 'utf-8'
            error_soup = BeautifulSoup(res.text, 'lxml')
            error_info = error_soup.select_one('h2+table td.text')
            if error_info:
                error_info = error_info.text
            else:
                error_info = error_soup.find('h1', text='上传失败！').find_next()
            error_info = '上传失败：{}'.format(error_info)
            raise ValueError(error_info)

    def worker(self):
        self._install_cookies()
        print('正在搜索猫站游戏列表...')
        self._find_game()
        if self.gid is None:
            print('未找到相关游戏，正在上传游戏资料...')
            if self._upload_game() is False:
                return 0
        print('正在上传种子...')
        self._upload_torrent()


if __name__ == '__main__':
    find_indie('刺客信条')
    # ggn = GGnApi('none')
    # ggn._download_torrent()
