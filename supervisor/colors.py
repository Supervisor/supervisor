ESC = '\033['


class ansicolors:
    class fg:
        black = ESC + '30m'
        red = ESC + '31m'
        green = ESC + '32m'
        yellow = ESC + '33m'
        blue = ESC + '34m'
        magenta = ESC + '35m'
        cyan = ESC + '36m'
        white = ESC + '37m'
        reset = ESC + '39m'

    class bg:
        black = ESC + '40m'
        red = ESC + '41m'
        green = ESC + '42m'
        yellow = ESC + '43m'
        blue = ESC + '44m'
        magenta = ESC + '45m'
        cyan = ESC + '46m'
        white = ESC + '47m'
        reset = ESC + '49m'

    class style:
        bright = ESC + '1m'
        dim = ESC + '2m'
        normal = ESC + '22m'
        reset_all = ESC + '0m'
