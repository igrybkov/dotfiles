"""Testinfra tests for default Molecule scenario."""


def test_home_directory_exists(host):
    """Verify home directory exists."""
    home = host.file("/root")
    assert home.exists
    assert home.is_directory


def test_config_directory_exists(host):
    """Verify .config directory exists."""
    config_dir = host.file("/root/.config")
    assert config_dir.exists
    assert config_dir.is_directory


def test_ssh_directory_exists(host):
    """Verify .ssh directory exists."""
    ssh_dir = host.file("/root/.ssh")
    assert ssh_dir.exists
    assert ssh_dir.is_directory
    # Note: permissions not enforced by dotfiles role, just verifying existence


def test_local_bin_directory_exists(host):
    """Verify .local/bin directory exists."""
    bin_dir = host.file("/root/.local/bin")
    assert bin_dir.exists
    assert bin_dir.is_directory


class TestDotfilesSymlinks:
    """Tests for dotfiles symlink management."""

    def test_gitconfig_is_symlink(self, host):
        """Verify .gitconfig is a symlink."""
        gitconfig = host.file("/root/.gitconfig")
        assert gitconfig.exists
        assert gitconfig.is_symlink
        assert gitconfig.linked_to == "/tmp/test-dotfiles/gitconfig"

    def test_zshrc_is_symlink(self, host):
        """Verify .zshrc is a symlink."""
        zshrc = host.file("/root/.zshrc")
        assert zshrc.exists
        assert zshrc.is_symlink
        assert zshrc.linked_to == "/tmp/test-dotfiles/zshrc"

    def test_config_nvim_is_symlink(self, host):
        """Verify .config/nvim is a symlink."""
        nvim = host.file("/root/.config/nvim")
        assert nvim.exists
        assert nvim.is_symlink
        assert nvim.linked_to == "/tmp/test-dotfiles/config/nvim"

    def test_config_fish_is_symlink(self, host):
        """Verify .config/fish is a symlink."""
        fish = host.file("/root/.config/fish")
        assert fish.exists
        assert fish.is_symlink
        assert fish.linked_to == "/tmp/test-dotfiles/config/fish"

    def test_bin_script_is_symlink(self, host):
        """Verify bin script is symlinked to .local/bin."""
        script = host.file("/root/.local/bin/test-script")
        assert script.exists
        assert script.is_symlink
        assert script.linked_to == "/tmp/test-bin/test-script"


class TestSSHConfig:
    """Tests for SSH configuration."""

    def test_ssh_config_exists(self, host):
        """Verify SSH config file exists."""
        ssh_config = host.file("/root/.ssh/config")
        assert ssh_config.exists
        assert ssh_config.is_file

    def test_ssh_config_permissions(self, host):
        """Verify SSH config has correct permissions."""
        ssh_config = host.file("/root/.ssh/config")
        assert ssh_config.mode == 0o600

    def test_ssh_config_contains_test_server(self, host):
        """Verify SSH config contains test server."""
        ssh_config = host.file("/root/.ssh/config")
        content = ssh_config.content_string
        assert "Host test-server" in content
        # ssh_config module uses lowercase directive names
        assert "hostname test.example.com" in content

    def test_ssh_config_has_blocks(self, host):
        """Verify SSH config has top and bottom blocks."""
        ssh_config = host.file("/root/.ssh/config")
        content = ssh_config.content_string
        # Top block (lowercase to match community.general.ssh_config normalization)
        assert "include ~/.ssh/custom_config" in content
        # Bottom block (lowercase to match community.general.ssh_config normalization)
        assert "serveraliveinterval 60" in content
