class Pdfcat < Formula
  desc "Terminal PDF reader optimized for Kitty graphics protocol"
  homepage "https://github.com/marromlam/pdfcat"
  url "https://github.com/marromlam/pdfcat/archive/refs/tags/v0.0.3.tar.gz"
  sha256 "29ef10fdd4fed7e9005ea70223924d64ae7b8e7bdbd1850a2110aabe1b0a50a3"
  license "MIT"
  head "https://github.com/marromlam/pdfcat.git", branch: "main"

  # Pin to 3.13 — Pillow (and other deps) don't have prebuilt wheels for
  # 3.14 yet, which forces a from-source build that needs jpeg/libtiff/etc.
  depends_on "python@3.13"

  def install
    python = Formula["python@3.13"].opt_bin/"python3.13"

    system python, "-m", "venv", libexec
    system libexec/"bin/python", "-m", "pip", "install", "--upgrade", "pip", "setuptools",
 "wheel"
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
