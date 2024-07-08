# coding: utf-8
import json
import socket
import argparse
import warnings
import tkinter as tk #GUIモジュール
import threading #スレッド処理モジュール

# プレイヤーの船を表すクラスである．
class Ship:
    MAX_HPS = {"w" : 3,
                "c" : 2,
                "s" : 1}
    def __init__(self,ship_type, position): 
        if not ship_type in Ship.MAX_HPS.keys():
            raise Exception("invalid type supecified")
        # 船の種類と最大HPを定義している．
        
        # 種類と座標とHPにアクセスできる．
        self.type = ship_type
        self.position = position
        self.hp = Ship.MAX_HPS[ship_type]

  # 座標を変更する．
    def moved(self,to):
        self.position = to

  # ダメージを受けてHPが減る．
    def damaged(self,d):
        self.hp -= d

    # 座標が移動できる範囲(縦横)にあるか確認する．
    def reachable(self,to):
        return self.position[0] == to[0] or self.position[1] == to[1]

    # 座標が攻撃できる範囲(自分の座標及び周囲1マス)にあるか確認する．
    def attackable(self,to):
        return abs(to[0] - self.position[0] <= 1) and abs(to[1] - self.position[1]) <= 1


# プレイヤーを表すクラスである．艦を複数保持している．
class Client:

    # フィールドの大きさを定義している．
    FIELD_SIZE = 5

    #
    # 艦種ごとに座標を与えられるので，Shipオブジェクトを作成し，連想配列に加える．
    # 艦のtypeがkeyになる．
    #
    def __init__(self,positions):
        self.ships = {}
        for ship_type, position in positions.items():
            if self.__overlap(position):
                raise Exception("given overlapping positions")
            if not Client.in_field(position):
                raise Exception("given overlapping positions")
            self.ships[ship_type] = Ship(ship_type, position)

    # 艦が座標に移動可能か確かめてから移動させる．相手プレイヤーに渡す情報を連想配列で返す．
    def move(self,ship_type, to):
        ship = self.ships[ship_type]

        if (ship is None) or (not Client.in_field(to)) or (not ship.reachable(to)) or (self.__overlap(to) is not None):
            return False

        distance = [to[0] - ship.position[0], to[1] - ship.position[1]]
        ship.moved(to)
        return {"ship":ship_type, "distance":distance}

    #
    # 攻撃された時の処理．攻撃を受けた艦，あるいは周囲1マスにいる艦を調べ，状態を更新する．
    # 相手プレイヤーに渡す情報を連想配列で返す．
    #
    def attacked(self,to):
        if not Client.in_field(to):
            return False

        info = {"position":to}
        ship = self.__overlap(to)
        near = self.__near(to)

        if not ship == None:
            ship.damaged(1)
            info["hit"] = ship.type
            if ship.hp == 0:
                del self.ships[ship.type]
        

        info["near"] = [s.type for s in near]

        return info

    # 艦の座標とHPを返す．meで自分かどうかを判定し，違うならpositionは教えない．
    def condition(self,me):
        cond = {}
        for ship in self.ships.values():
            cond[ship.type] = {"hp" : ship.hp}
            if me:
                cond[ship.type]["position"] = ship.position
        return cond

    # 艦隊の攻撃可能な範囲を返す．
    def attackable(self,to):
        return Client.in_field(to) and any([ship.attackable(to) for ship in self.ships.values()])

    # 与えられた座標にいる艦を返す．
    def __overlap(self,position):
        for ship in self.ships.values():
            if ship.position == position:
                return ship
        return None

    # 与えられた座標の周り1マスにいる艦を配列で返す．
    def __near(self,to):
        near = []
        for ship in self.ships.values():
            if ship.position != to and abs(ship.position[0] - to[0]) <= 1 and abs(ship.position[1] - to[1]) <= 1:
                near.append(ship)
        return near

    # 与えられた座標がフィールドないかどうかを返す．
    @staticmethod
    def in_field(position):
        return position[0] < Client.FIELD_SIZE and position[1] < Client.FIELD_SIZE and position[0] >= 0 and position[1] >= 0

#
# 処理を行うクラスである．プレイヤー2人を保持している． ．
#
class Server:

    #
    # プレイヤーの配列である．
    # 行動プレイヤーのインデックスをcとする．
    # 今プレイヤーが2人であるという前提なので， 待機プレイヤーのインデックスは1-cである．
    #

    # 両プレイヤーからJSONを受け取って初期配置を設定する．
    def __init__(self,json1, json2):
        self.clients = []
        self.clients.append(Client(json.loads(json1))) #loadsは文字列をパースする
        self.clients.append(Client(json.loads(json2)))

    # 初期配置をJSONで返す．
    def initial_condition(self,c):
        return [json.dumps(self.condition(c)), json.dumps(self.condition(1-c))] #dumpsは文字列にjson化する

    #
    # 可能かどうかチェックしてから攻撃，あるいは移動の処理を行い，両プレイヤーに結果を通知するJSONを作る．
    # JSONの配列を返す．0番目の要素が行動プレイヤー宛，1番目の要素が待機プレイヤー宛である．
    #
    def action(self,c, json_str):
        info = [{},{}]
        active = self.clients[c]
        passive = self.clients[1-c]
        act = json.loads(json_str)#loadsは文字列をパースする

        if "attack" in act.keys():
            to = act["attack"]["to"]

            if not active.attackable(to):
                result = False
            else:
                result = passive.attacked(to)

            info[c]["result"] = {"attacked":result}
            info[1-c]["result"] = {"attacked":result}

            if len(passive.ships) == 0:
                info[c]["outcome"] = True
                info[1-c]["outcome"] = False
        
        elif "move" in act.keys():
            result = active.move(act["move"]["ship"], act["move"]["to"])
            info[1-c]["result"] = {"moved":result}

        if not result:
            info[c]["outcome"] = False
            info[1-c]["outcome"] = True

        info[c] = {**info[c],**self.condition(c)}
        info[1-c] = {**info[1-c],**self.condition(1-c)}

        return [json.dumps(info[c]), json.dumps(info[1-c])] #dumpsは文字列に変換 

  # 自分と相手の状態を連想配列で返す．
    def condition(self,c):
        return {
            "condition" : {
                "me" : self.clients[c].condition(True),
                "enemy" : self.clients[1-c].condition(False)
            }
        }

# 処理結果をわかりやすくみせるためクラスとして実装
class VisualReporter:
    GRID_SIZE = 120
    DATA_UPDATE_CHECK_INTERVAL = 10
    QUIT_CHECK_INTERVAL = 1000
    def __init__(self,field_size):
        #フィールドの大きさを初期化
        self.field_size = field_size
        #windowを初期化
        self.window = tk.Tk()
        self.window.title("Submarine Game")
        self.window.geometry(f"{VisualReporter.GRID_SIZE*field_size}x{VisualReporter.GRID_SIZE*field_size}")
        
        #キャンバスを設置
        self.canvas = tk.Canvas(self.window,bg="#0022dd",height=VisualReporter.GRID_SIZE*field_size,width=VisualReporter.GRID_SIZE*field_size)
        
        #guiを終了するための関数を準備(https://qiita.com/shiracamus/items/cd1d5f2d8fabd4e8a366 を参考に)
        self.__willquit=False
        self.window.after(VisualReporter.QUIT_CHECK_INTERVAL, self.__quit_check)
        #割と何でも実行する関数を呼ぶ準備
        self.func_kwargs_list = []
        self.window.after(VisualReporter.DATA_UPDATE_CHECK_INTERVAL,self.__do_func_with_kwargs)
        
        #別のスレッドとしてguiを起動
        self.start_gui()
        self.window_thread = threading.Thread(target=self.start_gui)
        self.window_thread.start()
        
    def __do_func_with_kwargs(self):
        for func, kwargs in self.func_kwargs_list:
            func(**kwargs)
    
    def __quit_check(self):
        if self.__willquit:
            self.window.destroy()
        else :
            self.window.after(VisualReporter.QUIT_CHECK_INTERVAL, self.__quit_check)
        
    def start_gui(self):
        self.window.mainloop()        
    
    def __del__(self):
        self.__willquit = True
        self.window_thread.join()
    
    # 結果をアスキーアートで出力する．
    def report_field(self, result, c):
        results = [json.loads(result[0]), json.loads(result[1])]

        fleets = [results[c]["condition"]["me"], results[1-c]["condition"]["me"]]
        if results[1].get("result")== None:
            attacked = None
        else:
            attacked = None if results[1]["result"].get("attacked") == None else results[1]["result"]["attacked"]["position"]

        for _ in range(2):
            self.__print_in_cell("  ")
            for i in range(self.field_size):
                self.__print_in_cell(" " + str(i) + " ")
  
        self.__print_bars()
        for y in range(self.field_size):
            self.__print_in_cell(" " + str(y) + " ")
            for d in range(1+1):
                for x in range(self.field_size):
                    if d == 1-c and attacked == [x, y]:
                        print("!",end="")
                    else:
                        print(" ",end="")
                    s = True
                    for ship in fleets[d].items():
                        if ship[1]["position"] == [x, y]:
                            self.__print_in_cell(ship[0] + str(ship[1]["hp"]))
                            s = False
                            break
                    if s:
                        self.__print_in_cell("  ")
                if d == 0:
                    self.__print_in_cell("   ")
            self.__print_bars()
        print("\n",end="")

    # マスの縦線を描く．
    def __print_in_cell(self,s):
        print(s + "|",end="")

    # マスの横線を描く．
    def __print_bar(self):
        for _ in range(self.field_size):
            print("----",end="")

    # マスの横線をつなげて描く．
    def __print_bars(self):
        print("\n",end="")
        print("----",end="")
        self.__print_bar()
        print("   -",end="")
        self.__print_bar()
        print("\n",end="")

#状況をレポートするかどうかを定めるグローバル変数
verbose = True
#通信に用いるバッファサイズ
RECV_BUFFER_SIZE = 4096

#
# プレイヤーの行動をソケットから取得して処理し，結果を通知する．
# 勝利したプレイヤーを返す．勝敗が決していない時は-1を返す．
#
def one_action(active, passive, c, server, vr = VisualReporter(Client.FIELD_SIZE)):
    act = active.readline()
    act = act[:act.find('\n')]#改行文字以外がjsonとしての値
    results = server.action(c, act)
    if verbose:
        vr.report_field(results, c)
    active.write(results[0]+"\n")
    passive.write(results[1]+"\n")

    if "outcome" in json.loads(results[0]).keys():
        if json.loads(results[0])["outcome"]:
            return c
        else:
            return 1 - c
    else:
        return -1

# TCPコネクション上で処理を行う．
def main(args):
    #盤面の用意
    vr = VisualReporter(Client.FIELD_SIZE)
    
    #接続の確立
    warnings.warn(f"listening {args.ipaddr} {args.port}")
    tcp_server = socket.socket(socket.AF_INET,socket.SOCK_STREAM) #IPv4を用いてTCP通信をすることにする
    tcp_server.bind((args.ipaddr, args.port))                     #指定されたIPアドレスとポートを紐づける
    clients = []
    addresses = []
    #2つのclientと接続
    tcp_server.listen(2) 
    print("listening...")
    for i in range(2):
        tmp = tcp_server.accept()
        clients.append(tmp[0].makefile('rw',buffering=1))   #textfileのようなインターフェースを通じて通信 改行記号までが一つの通信として扱われる
        addresses.append(tmp[1])
        print(f"connected {i}")

    for client in clients:
        client.write("you are connected. please send me initial state.\n")

    server = Server(clients[0].readline(), clients[1].readline())

    #勝者を保持する変数
    winner = -1
    # バトル回数を保持する変数．
    i = 0
    # 行動プレイヤーを保持する変数．
    c = 0
    if verbose : 
        vr.report_field(server.initial_condition(c), c)
    while (winner == -1 and i < 10000):
        clients[c].write("your turn\n")
        clients[1-c].write("waiting\n")
        winner = one_action(clients[c], clients[1-c], c, server,vr=vr)
        c = 1 - c
        i += 1
    if winner == -1:
        for client in clients:
            client.write("even\n")
        print("even")
    else:
        clients[winner].write("you win\n")
        clients[1-winner].write("you lose\n")
        print("player" + str(1+winner) + " win")

    for client in clients:
        client.close()
    tcp_server.close()


parser = argparse.ArgumentParser()
parser.add_argument("ipaddr", default="127.0.0.1")
parser.add_argument("port", default=2000,type=int)
parser.add_argument("--quiet", action="store_true")

if __name__ == "__main__": #直接実行したときのみ処理を行う(__FILE__ == $0に対応)
    args = parser.parse_args()
    if args.quiet:
        verbose = False
    main(args)
