"""Menu tổng hợp điều hướng giữa discovery, chat và giao diện truyền file."""

from chat.chat_ui import ChatUI


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

    def display_main_menu(self):
        """Hiển thị menu tổng hợp và trả lựa chọn người dùng."""
        print("\n========== LAN CHAT & FILE SHARING ==========")
        print("1. Peer Discovery")
        print("2. Chat")
        print("3. File Manager")
        print("4. Exit")
        return input("Choose option: ").strip()

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
        """Lặp menu và điều hướng đến chức năng được chọn cho tới khi thoát."""
        while True:
            choice = self.display_main_menu()
            if choice == "1":
                self.display_peer_menu()
            elif choice == "2":
                self.display_chat_menu()
            elif choice == "3":
                self.display_file_menu()
            elif choice == "4":
                return
            else:
                print("Lựa chọn không hợp lệ. Vui lòng chọn từ 1 đến 4.")
