# typed: false
# frozen_string_literal: true

class Laziergit < Formula
  include Language::Python::Virtualenv

  desc "Even lazier git TUI with 3 big buttons: ADD, COMMIT, PUSH"
  homepage "https://github.com/yourname/laziergit"
  url "https://github.com/yourname/laziergit/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "MIT"
  version "1.0.0"

  depends_on "python@3.13"

  resource "textual" do
    url "https://files.pythonhosted.org/packages/source/t/textual/textual-8.2.6.tar.gz"
    sha256 "8c43b0b3326c4f77f609bb9f1a95daf00777808973bb3ebfb078767bc3a189d2"
  end

  resource "markdown-it-py" do
    url "https://files.pythonhosted.org/packages/source/m/markdown-it-py/markdown_it_py-3.0.0.tar.gz"
    sha256 "e3f60a94fa066dc52ec76661e37c851cb232dcef53e523b3c7d6f996d0a2a873"
  end

  resource "mdit-py-plugins" do
    url "https://files.pythonhosted.org/packages/source/m/mdit-py-plugins/mdit_py_plugins-0.4.1.tar.gz"
    sha256 "834b8ac23d1cd60cec703646ffd22ae97b7955a6d59eb6d664265fb53d89e3a9"
  end

  resource "mdurl" do
    url "https://files.pythonhosted.org/packages/source/m/mdurl/mdurl-0.1.2.tar.gz"
    sha256 "bb413d29f5eea38f31dd4754dd7377d4465116fb207585f97bf925588687c1ba"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/source/P/Pygments/pygments-2.18.0.tar.gz"
    sha256 "786ff802f32e91311bff3889f6e9a86e81505fe99f2735bb6d60ae0c5004f199"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.8.1.tar.gz"
    sha256 "8260cda28e3db6bf04d2d1ef4dbc03ba80a824c88b0e7668a0f23126a6eb2e7a"
  end

  resource "typing-extensions" do
    url "https://files.pythonhosted.org/packages/source/t/typing_extensions/typing_extensions-4.12.2.tar.gz"
    sha256 "1a7ead55c7e559dd4dee8856e3a88b41225abfe1ce8df57b7c13915fe121ffb8"
  end

  resource "platformdirs" do
    url "https://files.pythonhosted.org/packages/source/p/platformdirs/platformdirs-4.3.6.tar.gz"
    sha256 "357fb2acbc885b0419afd3ce3ed34564c35c4f7ae08ece1b8574e413b2d32a24"
  end

  resource "linkify-it-py" do
    url "https://files.pythonhosted.org/packages/source/l/linkify-it-py/linkify_it_py-2.0.3.tar.gz"
    sha256 "68cda27e162e9215c17d7866490401d2d63f2f13822b420731bbc0979b451ec2"
  end

  resource "uc-micro-py" do
    url "https://files.pythonhosted.org/packages/source/u/uc-micro-py/uc-micro-py-1.0.3.tar.gz"
    sha256 "d321b92cff673ec58027c04015fcaa8bb1e005478643ff4a500882eaee88ff87"
  end

  def install
    venv = virtualenv_create(libexec, "python3")
    venv.pip_install resources
    libexec.install "laziergit.py"
    (bin/"laziergit").write <<~SHELL
      #!/bin/bash
      exec "#{venv.root}/bin/python" "#{libexec}/laziergit.py" "$@"
    SHELL
  end

  test do
    assert_match "Not a git repository", shell_output("#{bin}/laziergit 2>&1 || true")
  end
end
