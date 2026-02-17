class Pdfcat < Formula
  desc "Terminal PDF reader optimized for Kitty graphics protocol"
  homepage "https://github.com/marromlam/pdfcat"
  license "MIT"
  head "https://github.com/marromlam/pdfcat.git", branch: "main"

  depends_on "python"

  def install
    python = Formula["python"].opt_bin/"python3"

    system python, "-m", "venv", libexec
    system libexec/"bin/python", "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"
    system libexec/"bin/pip", "install", buildpath

    bin.install_symlink libexec/"bin/pdfcat"
  end

  def caveats
    <<~EOS
      For best rendering support, use a Kitty-compatible terminal.

      Optional tool for external compatibility checks:
        brew install timg
    EOS
  end

  test do
    assert_match "Usage:", shell_output("#{bin}/pdfcat -h")
  end
end
