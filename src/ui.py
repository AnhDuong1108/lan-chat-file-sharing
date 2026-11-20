"""Menu tổng hợp điều hướng giữa discovery, chat và giao diện truyền file."""

from chat.chat_ui import ChatUI
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style

class UI:
    def __init__(
        self, peer_manager, chat_manager, file_manager, *,
        chat_ui=None, file_ui=None, set_status=None,
    ):
        """
        Nhận các manager và FileUI được tạo bên ngoài với cùng file_manager.

        :param file_ui: Đối tượng có start(). Để None khi FileUI chưa được tích hợp.
        :param chat_ui: ChatUI đã được nối với FileManager bởi mã tích hợp của Issue 2.
        :param set_status: Callback đổi trạng thái UDP cho ChatUI.
        """
        self.peer_manager = peer_manager
        self.chat_manager = chat_manager
        self.file_manager = file_manager
        self.chat_ui = chat_ui if chat_ui is not None else ChatUI(peer_manager, chat_manager, set_status)
        self.file_ui = file_ui

        self.style = Style.from_dict({
                "prompt": "#00ff87 bold",
                "command": "#00afff bold",
                "success": "#00ff91",
                "error": "#ff5f5f bold",
                "warning": "#ffaf00",
                "system": "#888888",
                "peer": "#5fd7ff bold",
                "timestamp": "#888888 italic",
            })
        self.session = PromptSession(style=self.style,
                                        erase_when_done=True)

    def get_choice(self) -> str:
        if self.session is not None:
            try:
                choice = self.session.prompt([("class:choice", "[?] ")])
            except Exception:
                choice = input("[?] ")
        else:
            choice = input("[?] ")

        return choice.strip() 

    def display_main_menu(self):
        """Display the main menu and prompt the user for a command."""
        print("\n ================ MAIN MENU ===============")
        print("/chat          - Open Chat")
        print("/files         - Open File Manager")
        print("/quit          - Exit the program")
        print("/help          - Show all commands")
        print("==============================================")


    # phần này là /list trong chat
    def display_peer_menu(self):
        """Hiển thị các peer đã phát hiện, gồm cả trạng thái away và offline."""
        peers = self.peer_manager.get_all_peers()
        if not peers:
            print("Chưa tìm thấy peer nào.")
        for index, peer in enumerate(peers, start=1):
            print(
                f"{index}. {peer['username']} ({peer['ip']}:{peer['tcp_port']}) "
                f"- {peer['status']}"
            )

    def display_chat_menu(self):
        """Chuyển đến menu ChatUI. Khi thoát chat, quay lại menu tổng hợp."""
        self.chat_ui.start()

    def display_file_menu(self):
        """Chuyển đến FileUI đã được tích hợp với FileManager."""
        if self.file_manager is None:
            print("Chức năng này cần tích hợp FileManager, FileServer và FileUI.")
            return
        if self.file_ui is None:
            from file_transfer.file_ui import FileUI

            self.file_ui = FileUI(
                self.file_manager, self.chat_manager, self.peer_manager, self.chat_ui
            )
        self.file_ui.start()

    def start(self):
        first = True
        print("\n========== LAN CHAT & FILE SHARING ==========")
        self.display_main_menu()
        """Lặp menu và điều hướng đến chức năng được chọn cho tới khi thoát."""
        while True:
            if not first:
                print("================ MAIN MENU ===============")
            first = False

            choice = self.get_choice()
            if choice == "/chat":
                self.display_chat_menu()
            elif choice == "/files":
                self.display_file_menu()
            elif choice == "/quit":
                return
            elif choice == "/help":
                self.display_main_menu()
            else:
                print("Invalid option. Please try again.")
