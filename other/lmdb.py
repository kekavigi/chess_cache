from pickle import dumps as pdump
from pickle import loads as pload

import lmdb


class LMDB:
    def __init__(self, path: str):
        self.db = lmdb.Environment(path, readahead=False, map_size=2**20)
        self.path = path

    def __getitem__(self, key):
        with self.db.begin() as tx:
            result = tx.get(pdump(key))
        if result is None:
            raise KeyError(key)
        return pload(result)

    def __setitem__(self, key, val):
        with self.db.begin(write=True) as tx:
            result = tx.put(pdump(key), pdump(val))
        return result

    def __delitem__(self, key):
        with self.db.begin(write=True) as tx:
            cur = tx.cursor()
            seek = cur.set_key(pdump(key))
            if not seek:
                raise KeyError(key)
            cur.delete()

    def __contains__(self, key):
        with self.db.begin() as tx:
            cur = tx.cursor()
            return cur.set_key(pdump(key))

    def __iter__(self):
        with self.db.begin() as tx:
            cur = tx.cursor()
            cur.first()
            for _key in cur.iternext(keys=True, values=False):
                yield pload(_key)

    def __reversed__(self):
        raise NotImplementedError

    def __len__(self):
        return self.db.stat()["entries"]

    def __sizeof__(self):
        return self.db.stat()["psize"]

    def __repr__(self):
        return f'<LMDB "{self.path}"; {self.__len__()} entries>'

    def get(self, key, default=None):
        with self.db.begin() as tx:
            result = tx.get(pdump(key), default=default)
        if result == default:
            return default
        return pload(result)

    def pop(self, key):
        with self.db.begin(write=True) as tx:
            cur = tx.cursor()
            seek = cur.set_key(pdump(key))
            if not seek:
                raise KeyError(key)
            return pload(cur.pop(pdump(key)))

    def popitem(self):
        with self.db.begin(write=True) as tx:
            cur = tx.cursor()
            seek = cur.last()
            if not seek:
                raise KeyError("popitem(): Database is empty")
            _key = cur.key()
            _val = cur.pop(_key)
            return pload(_key), pload(_val)

    def update(self, iterable):
        if hasattr(iterable, "keys"):
            iterable = [(pdump(key), pdump(iterable[key])) for key in iterable.keys()]
        else:
            iterable = [(pdump(key), pdump(val)) for key, val in iterable]
        with self.db.begin(write=True) as tx:
            cur = tx.cursor()
            cur.putmulti(iterable)

    def setdefault(self, key, default=None):
        with self.db.begin() as tx:
            result = tx.get(pdump(key))
        if result is None:
            tx.put(pdump(key), pdump(default))
            return default
        return pload(result)

    def clear(self):
        with self.db.begin(write=True) as tx:
            db = self.db.open_db()
            tx.drop(db)

    def keys(self):
        return self.__iter__()

    def values(self):
        with self.db.begin() as tx:
            cur = tx.cursor()
            cur.first()
            for _val in cur.iternext(keys=False, values=True):
                yield pload(_key)

    def items(self):
        with self.db.begin() as tx:
            cur = tx.cursor()
            cur.first()
            for _key, _val in cur.iternext(keys=True, values=True):
                yield pload(_key), pload(_val)

    def transact(self, write=False):
        return self.db.begin(write=write)

    def close(self):
        self.db.close()

    def __eq__(self, o):
        raise NotImplementedError

    def __ne__(self, o):
        raise NotImplementedError

    def __le__(self, o):
        raise NotImplementedError

    def __ge__(self, o):
        raise NotImplementedError

    def __or__(self, o):
        raise NotImplementedError

    def __ior__(self, o):
        raise NotImplementedError

    def fromkeys(self, iterable, value=None):
        # not relevant
        raise NotImplementedError

    def copy(self):
        # not relevant
        raise NotImplementedError
