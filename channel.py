# fm.model
# coding:utf-8

from MySQLdb import IntegrityError as _IntegrityError
from corelib.mixin.props import PropsMixin
from corelib.sqlstore import store
from corelib.mc import mc, ver_mc, ONE_HOUR
from corelib.doubandb import db
from corelib.utils import cache
from corelib.config import DEVELOP_MODE

from fm.model.open_channel.channel import Channel
from fm.model.song import RadioSong
from fm.model.consts import (PERSONAL_CHANNEL, ONE_WEEK, HALF_DAY,
        CHANNEL_TYPE_COMMERCIAL, CHANNEL_TYPE_HIDE, CHANNEL_TYPE_NORMAL,
        CHANNEL_TYPE_AUTOMOBILE, CHANNEL_TYPE_SPECIAL_DEVICE, CHANNEL_TYPE_ALL,
        CHANNEL_TRACK_SET_DBKEY)


SPECIAL_WEB_CHANNEL_LIST = [
    {"channel_id": 0, "name": "私人兆赫"},
    {"channel_id": -3, "name": "红心兆赫"}
]

MC_KEY_RADIO_CHANNEL = "fm:channel:%s:v2"
MC_KEY_COMMERCIAL_CHANNEL_IDS = 'fm:channel:commercial_ids'
MC_KEY_PUBLIC_CHANNEL_IDS = 'fm:channel:public_ids'
MC_KEY_HIDDEN_CHANNEL_IDS = 'fm:channel:hidden_ids'
MC_KEY_ALL_PUBLISHED_CHANNEL_IDS = 'fm:channel:published_ids'
MC_KEY_ALL_PUBLIC_CHANNEL_IDS = "radio_channel_id_list"
MC_KEY_SONG_PRIORITY_LIST = 'fm:channel:%s:song_priority_list_v2'
MC_KEY_GET_CHANNELS_NOT_TYPE = "fm:channels:get_channels_not_type:%s"


def web_chan_list():
    channels = RadioChannel.get_channels(CHANNEL_TYPE_NORMAL |
                                         CHANNEL_TYPE_COMMERCIAL,
                                         only_published=True)
    return ([{"channel_id": int(c.channel),
             "name": c.name
            } for c in channels if not c.is_hidden and not c.is_special_device]
            + SPECIAL_WEB_CHANNEL_LIST)


def client_chan_list(app_name, client):
    is_pateo = (app_name == "radio_pateo")  # 以后此类需求使用client进行区别
    client_memo = client.get("o")
    is_bmw = client_memo and \
        (client_memo == "bmw" or client_memo.startswith("bmw_"))
    chs = []
    exclusive_chan = None

    for c in _get_chs_not_type("hidden"):

        if (is_pateo or is_bmw) and has_type(c, "automobile"):
            continue

        if has_type(c, "special_device"):
            if client == {} or client.get("e") not in \
                    c.get("device", "").split("|"):
                continue

        if c.get("exclude", "") != "":
            exclusive_chan = c

        chs.append(c.copy())

    if exclusive_chan:
        del_chs = get_chs_by_type(exclusive_chan.get("exclude"))
        for c in del_chs:
            if c in chs and c != exclusive_chan:
                chs.remove(c)

    for i, c in enumerate(chs):
        c['seq_id'] = i
        c['type'] = c['exclude'] = c['device'] = None
        del c['type']
        del c['exclude']
        del c['device']

    chs.insert(0, {"name":"私人兆赫","seq_id":0,"abbr_en":"My","channel_id":0,"name_en":"Personal Radio"})
    ret = {"channels": chs}

    return ret

def get_ch_ids(t):
    t_array = t.split("|")
    channel_ids = []
    if "hidden" in t_array:
        channel_ids.extend(RadioChannel.get_hidden_channel_ids())
    if "commercial" in t_array:
        channel_ids.extend(RadioChannel.get_commercial_channel_ids())
    if "public" in t_array:
        channel_ids.extend(RadioChannel.get_public_channel_ids())

    return channel_ids


def get_chs_by_type(t):
    channel_ranks = Channel._get_channel_ranks()
    channel_ranks[PERSONAL_CHANNEL] = -1

    channels = RadioChannel.get_multi(get_ch_ids(t))
    channels.sort(key=lambda chl: channel_ranks.get(chl.channel,
                  1000000))
    for c in channels:
        if c.name and c.name.endswith("MHz"):
            c.name = c.name[0: -3]
        if c.name_en and c.name_en.endswith("MHz"):
            c.name_en = c.name_en[-3: 0]

    return [{"channel_id": c.channel, "name": c.name, "name_en": c.name_en,
            "abbr_en": c.abbr_en, "type": t} for c in channels]


@cache(MC_KEY_GET_CHANNELS_NOT_TYPE % '{t}', ONE_HOUR)
def _get_chs_not_type(t):
    channel_ranks = Channel._get_channel_ranks()
    channel_ranks[PERSONAL_CHANNEL] = -1

    channel_ids = get_ch_ids(t)
    all_channel_ids = RadioChannel.get_published_channel_ids()
    rest_channel_ids = set(all_channel_ids)-set(channel_ids)
    channels = filter(None, RadioChannel.get_multi(rest_channel_ids))
    channels.sort(key=lambda chl: channel_ranks.get(chl.channel, 1000000))

    filtered_channels = []
    for c in channels:
        ttype = []
        if c.channel_type & CHANNEL_TYPE_COMMERCIAL > 0:
            ttype.append("commercial")
        elif c.channel_type & CHANNEL_TYPE_NORMAL > 0:
            ttype.append("public")
        if c.channel_type & CHANNEL_TYPE_HIDE > 0:
            ttype.append("hidden")
        if c.channel_type & CHANNEL_TYPE_AUTOMOBILE > 0:
            ttype.append("automobile")
        if c.channel_type & CHANNEL_TYPE_SPECIAL_DEVICE > 0:
            ttype.append("special_device")
        if c.name.endswith("MHz"):
            c.name = c.name[0:-3]
        filtered_channels.append({"channel_id": c.channel, "name": c.name, "name_en": c.name_en,
            "abbr_en": c.abbr_en, "type": "|".join(ttype)})

    return filtered_channels


def has_type(channel, t):
    return t in channel.get("type", "").split("|")


class RadioChannel(PropsMixin):
    # 所有的公共兆赫默认状态会将豆瓣FM设置成关联小站
    # !基于这个前提!
    # 将公共兆赫存到open_channel时 将creator_id设成1也不会有问题
    PUBLIC_CHL_CREATOR_ID = 1
    STATUS_PUBLISHED = 'P'
    STATUS_OFFLINE = 'N'

    def __init__(self, id, channel, name, genre, desc,
                 channel_type, status):
        self.id = str(id)
        self.channel = str(channel)
        self.name = name
        self.genre = genre
        self.desc = desc
        self.channel_type = channel_type
        self.status = status

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.id == other.id

    def get_uuid(self):
        return '/fm/%s/%s' % (self.__class__.__name__, self.id)

    @property
    @cache(MC_KEY_SONG_PRIORITY_LIST % '{self.channel}')
    def song_priority_list(self):
        rs = store.execute('select list from radio_public_list '
                           'where channel=%s' % self.channel)

        if rs and rs[0][0]:
            return decode_song_priority_str(rs[0][0])

        return []

    def set_song_priority_list(self, song_priority_list):
        song_priority_list = filter(None, song_priority_list)
        store.execute('update radio_public_list set list="%s" '
                      'where channel=%s' %
                      (assemble_song_priority_list(song_priority_list),
                       self.channel))
        store.commit()
        mc.delete(MC_KEY_SONG_PRIORITY_LIST % self.channel)

    @classmethod
    @cache(MC_KEY_RADIO_CHANNEL % '{channel_id}', ONE_WEEK)
    def get(cls, channel_id):
        rs = store.execute("SELECT id, channel, name, genre, `desc`, "
                           "channel_type, status "
                           "FROM radio_public_list WHERE channel=%s",
                           channel_id)

        if rs:
            id, channel, name, genre, desc, channel_type, status = rs[0]
            return cls(id, channel, name, genre, desc, channel_type, status)

    @classmethod
    def get_multi(cls, channel_ids, only_published=True):
        cached_channels_dct = mc.get_multi([
            MC_KEY_RADIO_CHANNEL % id_ for id_ in channel_ids
        ])
        int_cids_not_cached = [
            int(cid) for cid in channel_ids
            if MC_KEY_RADIO_CHANNEL % cid not in cached_channels_dct
        ]

        if int_cids_not_cached:
            safe_sql_ids = ",".join([str(id_) for id_ in int_cids_not_cached])
            rs = store.execute(
                "SELECT id, channel, name, genre, `desc`, "
                "channel_type, status "
                "FROM radio_public_list WHERE channel "
                "IN (%s)" % safe_sql_ids
            )
            new_channels_dct = {}

            for r in rs:
                cid = r[1]
                new_channels_dct[MC_KEY_RADIO_CHANNEL % cid] = cls(*r)
            mc.set_multi(new_channels_dct, ONE_WEEK)
            cached_channels_dct.update(new_channels_dct)

        iter_channels = (
            cached_channels_dct.get(MC_KEY_RADIO_CHANNEL % cid)
            for cid in channel_ids
        )
        if only_published:
            return [c for c in iter_channels if c and c.status == 'P']
        return list(iter_channels)

    @classmethod
    @cache(MC_KEY_ALL_PUBLIC_CHANNEL_IDS, ONE_WEEK)
    def channel_id_list(cls):
        rs = store.execute("select channel from radio_public_list")
        return [channel_id for channel_id, in rs]

    @property
    def song_id_list(self):
        return [song_priority[0] for
                song_priority in self.song_priority_list]

    @property
    def song_num(self):
        return len(self.song_priority_list)

    @property
    def is_published(self):
        if self.status == self.STATUS_OFFLINE:
            return False
        open_channel = self.get_open_channel()
        if not open_channel:
            return True

        return open_channel.is_published

    @property
    def intro(self):
        open_channel = self.get_open_channel()
        return open_channel.intro

    @property
    def is_commercial(self):
        return self.channel_type & CHANNEL_TYPE_COMMERCIAL > 0

    @property
    def is_automobile(self):
        return self.channel_type & CHANNEL_TYPE_AUTOMOBILE > 0

    @property
    def is_special_device(self):
        return self.channel_type & CHANNEL_TYPE_SPECIAL_DEVICE > 0

    @property
    def is_hidden(self):
        return self.channel_type & CHANNEL_TYPE_HIDE > 0

    @property
    def excluded_type(self):
        return self.props.get('exclude', None)

    @property
    def name_en(self):
        return self.props.get('name_en', '')

    @property
    def abbr_en(self):
        return self.props.get('abbr_en', '')

    @property
    def device(self):
        return self.props.get('device', [])

    def publish(self):
        open_channel = self.get_open_channel()
        open_channel.publish()

        store.execute('update radio_public_list set status=%s '
                      'where id=%s', (self.STATUS_PUBLISHED, self.id))
        store.commit()
        flush_channel_mcs()
        mc.delete(MC_KEY_RADIO_CHANNEL % self.channel)
        self.status = self.STATUS_PUBLISHED

        return self

    def take_offline(self):
        open_channel = self.get_open_channel()
        open_channel.recall()

        store.execute('update radio_public_list set status=%s '
                      'where id=%s', (self.STATUS_OFFLINE, self.id))
        store.commit()
        flush_channel_mcs()
        mc.delete(MC_KEY_RADIO_CHANNEL % self.channel)
        self.status = self.STATUS_OFFLINE

        return self

    def rename(self, name):
        self.update(name=name)
        open_channel = self.get_open_channel()
        open_channel.update(name=name)

        return self

    def update_intro(self, intro):
        open_channel = self.get_open_channel()
        open_channel.update(intro=intro)

        return self

    def update(self, desc=None, song_priority_list=None, name=None,
               channel_type=None):
        desc = desc or self.desc
        name = name or self.name
        channel_type = channel_type or self.channel_type

        store.execute('update radio_public_list '
                      'set name=%s, `desc`=%s, channel_type=%s '
                      'where channel=%s',
                      (name, desc, channel_type, self.channel))
        store.commit()
        self.desc = desc
        self.name = name
        self.channel_type = channel_type
        mc.delete("radio_channel:%s" % self.channel)
        flush_channel_mcs()

    def add_songs(self, song_id_list):
        song_id_list = [id for id in song_id_list if id and
                        id not in self.song_id_list]
        if song_id_list:
            # omit the repeated items in song_id_list
            song_id_list = list(set(song_id_list))
            # new channel list
            list_to_add = [assemble_priority(id) for id in song_id_list]

            song_priority_list = self.song_priority_list
            song_priority_list.extend(list_to_add)
            self.set_song_priority_list(song_priority_list)

            mc.delete(Channel.KEY_CHANNEL_SONG_NUM % self.channel)

            return str(len(song_id_list))

        return "0"

    def delete_songs(self, song_id_list):
        # check if the song already exists.
        song_id_list = [id for id in song_id_list if id in
                        self.song_id_list]
        total_removed = 0

        new_song_priority_list = []
        if song_id_list and self.song_priority_list:
            # if id in list does not appear in song_id_list to delete,
            # reserve it in new list
            for song_priority in self.song_priority_list:
                if song_priority[0] not in song_id_list:
                    new_song_priority_list.append(song_priority)

            total_removed = self.song_num - len(new_song_priority_list)

            self.set_song_priority_list(new_song_priority_list)

        return str(total_removed)

    @classmethod
    def save_new_channel(cls, name, desc, song_id_list,
                         channel_type=CHANNEL_TYPE_NORMAL, channel_id=None):
        if channel_id is None:
            try:
                channel_id = 1 + max(int(c.channel)
                                     for c in RadioChannel.get_channels())
            except ValueError:
                channel_id = 1

        assembled_song_priority_list = ''
        # Assemble song_priority list to string
        if song_id_list:
            song_priority_list = [assemble_priority(id) for
                                  id in song_id_list]
            assembled_song_priority_list = assemble_song_priority_list(song_priority_list)

        if channel_id and name and desc:
            store.execute("""insert into radio_public_list
                (channel, name, genre,`desc`, list, channel_type) values
                (%s, %s, %s, %s, %s, %s)""", (channel_id, name, '', desc,
                                              assembled_song_priority_list, channel_type))
            store.commit()
            mc.delete("radio_channel:%s" % channel_id)
            mc.delete("publist_%s" % channel_id)
            mc.delete(MC_KEY_ALL_PUBLIC_CHANNEL_IDS)

            # 同时添加一个open_channel记录 作用是
            # * 用open_channel来存储封面信息
            # * 索引统一使用open_channel表的信息创建
            #   * 曲目信息存放位置不同, 像曲目流派索引这类的需要特殊处理
            channel = cls.get(channel_id)
            channel.save_as_open_channel()

            return channel_id

    def save_as_open_channel(self):
        name = self.name
        if name.lower().endswith("mhz"):
            # 线上的兆赫名很多以MHZ结尾 在这里需要检查去掉
            name = name[:-3]
        try:
            Channel.add(id=self.channel, name=name, intro="",
                        creator_id=self.PUBLIC_CHL_CREATOR_ID,
                        related_site_id=self._get_default_related_site_id())
        except _IntegrityError:
            # TODO 更新内容?
            pass

    @classmethod
    def _get_default_related_site_id(cls):
        site_id = 500836  # FM小站
        if DEVELOP_MODE:
            from luzong.site import Site
            s = Site.get("douban.fm")
            site_id = s.id if s else None
        return site_id

    def get_open_channel(self):
        return Channel.get(self.channel)

    @classmethod
    def get_channels(cls, channel_type=None, only_published=False):
        channel_ids = cls.channel_id_list()
        channels = [cls.get(i) for i in channel_ids]
        if not channel_type or not isinstance(channel_type, int):
            return channels

        rs = []
        for c in channels:
            if only_published and not c.is_published:
                continue
            if c.channel_type & channel_type > 0:
                rs.append(c)

        return rs

    @classmethod
    @cache(MC_KEY_PUBLIC_CHANNEL_IDS, ONE_WEEK)
    def get_public_channel_ids(cls):
        rs = store.execute('select channel from radio_public_list '
                           'where channel_type = %s '
                           'and status=%s '
                           'and channel != 0 '
                           'order by channel desc',
                           (CHANNEL_TYPE_NORMAL, cls.STATUS_PUBLISHED))

        return [r[0] for r in rs]

    @classmethod
    @cache(MC_KEY_HIDDEN_CHANNEL_IDS, ONE_WEEK)
    def get_hidden_channel_ids(cls):
        rs = store.execute('select channel from radio_public_list '
                           'where (channel_type & %s > 0) '
                           'and status=%s '
                           'and channel != 0 '
                           'order by channel desc',
                           (CHANNEL_TYPE_HIDE, cls.STATUS_PUBLISHED))

        return [r[0] for r in rs]

    @classmethod
    @cache(MC_KEY_COMMERCIAL_CHANNEL_IDS, ONE_WEEK)
    def get_commercial_channel_ids(cls):
        rs = store.execute('select channel from radio_public_list '
                           'where (channel_type & %s > 0) '
                           'and status=%s '
                           'and channel != 0 '
                           'order by channel desc',
                           (CHANNEL_TYPE_COMMERCIAL, cls.STATUS_PUBLISHED))

        return [r[0] for r in rs]

    @classmethod
    @cache(MC_KEY_ALL_PUBLISHED_CHANNEL_IDS, ONE_WEEK)
    def get_published_channel_ids(cls):
        rs = store.execute('select channel from radio_public_list '
                           'where status=%s '
                           'and channel != 0 '
                           'order by channel desc',
                           cls.STATUS_PUBLISHED)

        return [r[0] for r in rs]

    @classmethod
    def chans_name_map(cls):
        return dict([(str(c.id),
                c.name if c.id == 0 else
                c.name + ' MHz') for c in
                RadioChannel.get_multi(RadioChannel.get_published_channel_ids())])

def flush_channel_mcs():
    mc.delete(MC_KEY_COMMERCIAL_CHANNEL_IDS)
    mc.delete(MC_KEY_PUBLIC_CHANNEL_IDS)
    mc.delete(MC_KEY_HIDDEN_CHANNEL_IDS)
    mc.delete(MC_KEY_ALL_PUBLISHED_CHANNEL_IDS)


def assemble_song_priority_list(song_priority_list):
    # assemble song_priority_list in to string
    return "|".join("%s:%s" % (song_id, priority) for
                    (song_id, priority) in song_priority_list)


def decode_song_priority_str(song_priority):
    # decode song_priority string into list
    return [song_priority_str.split(":") for
            song_priority_str in song_priority.split("|")]


def assemble_priority(song_id):
    '''
        assemble the song id and priority into a list.
        list structure: [song_id, priority]
    '''
    song = RadioSong.get(song_id)
    if not song:
        return None
    return [song_id, 1]


def get_channel_ranks():
    rows = get_channel_metas()
    return {channel_id: rank for channel_id, rank, _ in rows}


def get_channel_scores():
    rows = get_channel_metas()
    return {channel_id: score for channel_id, _, score in rows}


def channel_ids_for_dj_party():
    channels = RadioChannel.get_channels(CHANNEL_TYPE_COMMERCIAL | CHANNEL_TYPE_HIDE, True)
    return [int(c.channel) for c in channels]

def channel_ids_for_dj_public():
    channels = RadioChannel.get_channels(CHANNEL_TYPE_NORMAL, True)
    return [int(c.channel) for c in channels]

KEY_CHANNEL_METAS = "fm:channels:metas"


@cache(KEY_CHANNEL_METAS, HALF_DAY)
def get_channel_metas():
    """从channel_chart表中获取最新的频道rank值和score值和score值
    rank值可用于频道排序
    score值可用于加权随机选择默认频道
    """
    return store.execute("SELECT channel_id, rank, score FROM channel_chart "
                         "WHERE seq_id = (SELECT MAX(seq_id) FROM channel_chart) "
                         "GROUP BY channel_id")


def record_channel_clicks(uid, cid, ctype):
    CTYPES = ['r', 'c']  # recent, collected
    if ctype not in CTYPES:
        return
    if not cid:
        return

    store.execute('insert into channel_picking_record '
                  '(uid, cid, ctype) '
                  'values (%s, %s, %s)', (uid, cid, ctype))
    store.commit()


# SEE: http://code.dapps.douban.com/fm/issues/23/
_MCKEY_SONG_ID_SET_IN_CHANNEL = 'fm:channel:%s:song_id_set:ver_cache'


def get_song_id_set_in_public_channel(cid, default=set()):
    cached = ver_mc.get(_MCKEY_SONG_ID_SET_IN_CHANNEL % cid)
    if cached is not None:
        return cached
    song_id_set = db.get(CHANNEL_TRACK_SET_DBKEY % cid, default)
    ver_mc.set(_MCKEY_SONG_ID_SET_IN_CHANNEL % cid, song_id_set)
    return song_id_set


def set_song_id_set_in_public_channel(cid, song_id_set):
    db.set(CHANNEL_TRACK_SET_DBKEY % cid, song_id_set)
	ver_mc.delete(_MCKEY_SONG_ID_SET_IN_CHANNEL % cid)
