import unittest
import torch

from janus_model.model import ByteTokenizer, JanusModelConfig, JanusTinyTransformer, parameter_count


class JanusNativeModelTests(unittest.TestCase):
    def test_byte_tokenizer_roundtrip(self):
        text = "JANUS REMEMBERS THE REGISTRY"
        ids = ByteTokenizer.encode(text, bos=True, eos=True)
        self.assertEqual(ids[0], ByteTokenizer.BOS)
        self.assertEqual(ids[-1], ByteTokenizer.EOS)
        self.assertEqual(ByteTokenizer.decode(ids), text)

    def test_forward_and_loss(self):
        torch.manual_seed(7)
        model = JanusTinyTransformer(JanusModelConfig())
        x = torch.randint(0, ByteTokenizer.vocab_size, (2, 32))
        y = torch.randint(0, ByteTokenizer.vocab_size, (2, 32))
        logits, loss = model(x, y)
        self.assertEqual(tuple(logits.shape), (2, 32, ByteTokenizer.vocab_size))
        self.assertTrue(torch.isfinite(loss))
        self.assertGreater(parameter_count(model), 100_000)


if __name__ == "__main__":
    unittest.main()
