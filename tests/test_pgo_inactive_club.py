import importlib
import json
from pathlib import Path
import unittest


class ClubInactiveTests(unittest.TestCase):
    def parse(self, body, headline='Jets List Five Inactives', team='NYJ', game=None, source_team=None):
        try:
            module = importlib.import_module('pgo_inactive_club')
        except ModuleNotFoundError:
            self.fail('The bounded club inactive body extractor is not implemented')
        return module.parse_club_body(body, headline, source_team or team, team, game or {'home':'TEN','away':'NYJ'})

    def test_six_actual_complete_lists_exclude_narrative_and_opponents(self):
        fixtures = json.loads((Path(__file__).parent/'fixtures/pgo_availability_v3_articles.json').read_text(encoding='utf-8'))
        expected = {'ATL':6,'BUF':7,'HOU':6,'CLE':7,'NYJ':5,'CIN':7}
        for item in fixtures:
            team = item['source_team']; article = item['article']
            if team not in expected: continue
            _, _, away, home = item['game_id'].split('_')
            with self.subTest(team=team):
                result = self.parse(article['articleBody'],article['headline'],team,{'home':home,'away':away})
                rows = result['observations']
                self.assertEqual(len(rows),expected[team]); self.assertEqual(result['unparsed_lines'],[])
                self.assertTrue(all(row['position'] == row['position'].upper() for row in rows))
                self.assertFalse({'Jason Sanders','Greg Dortch','Frank Gore Jr.','Cooper Rush'} & {row['name'] for row in rows})
                if team == 'CLE': self.assertEqual(rows[0]['status'],'EMERGENCY_QB')
                if team == 'NYJ': self.assertEqual(rows[2]['position'],'EDGE')
                if team == 'CIN': self.assertEqual(rows[-1]['name'],'Landon Robinson')
                if team == 'HOU': self.assertEqual(rows[-1]['name'],'Jaden Crumedy')

    def test_count_mismatch_duplicate_and_malformed_row_reject(self):
        for body,headline in [
            ('Jets Inactives\nK Blake Grupe','Jets List Five Inactives'),
            ('Jets Inactives\nK Blake Grupe\nK Blake Grupe','Jets Inactives'),
            ('Jets Inactives\nK Blake Grupe\nXX Mystery Player\nRB Kene Nwangwu','Jets Inactives'),
            ('Jets Inactives\nK Blake Grupe\nJets Inactives\nRB Kene Nwangwu','Jets Inactives')]:
            with self.subTest(body=body), self.assertRaises(ValueError): self.parse(body,headline)

    def test_prose_and_opponent_only_are_not_complete_club_lists(self):
        for body in ['Five Jets defensive players are inactive today. Joseph Ossai is inactive.',
                     'Tennessee Titans Inactives\nQB Other Player',
                     'K Blake Grupe\nRB Kene Nwangwu']:
            with self.subTest(body=body), self.assertRaises(ValueError): self.parse(body)

    def test_declared_list_stops_before_active_elevation_and_next_club(self):
        result = self.parse("The club has placed two players on today's inactive list:\nK Blake Grupe\nQB Alex Backup (emergency third quarterback)\n\nK Jason Sanders was elevated from the practice squad.\nTennessee Titans\nQB Other Player",'Jets List Two Inactives')
        self.assertEqual([row['name'] for row in result['observations']],['Blake Grupe','Alex Backup'])
        self.assertEqual(result['observations'][1]['status'],'EMERGENCY_QB')

    def test_opponent_generic_intro_cannot_be_reassigned(self):
        with self.assertRaises(ValueError):
            self.parse("The club has placed two players on today's inactive list:\nK Blake Grupe\nRB Kene Nwangwu",'Jets List Two Inactives',team='TEN',source_team='NYJ')

    def test_additional_six_actual_sources_and_only_explicit_opponent_lists(self):
        fixtures = json.loads((Path(__file__).parent/'fixtures/pgo_availability_v3_articles.json').read_text(encoding='utf-8'))
        expected = {'IND':{'IND':6},'CAR':{'CAR':7,'CHI':6},'TB':{'TB':7},'PIT':{'PIT':6,'ATL':6},'NO':{'NO':7,'DET':5},'TEN':{'TEN':7}}
        for item in fixtures:
            source = item['source_team']; article = item['article']
            if source not in expected: continue
            _, _, away, home = item['game_id'].split('_')
            for target in (away,home):
                with self.subTest(source=source,target=target):
                    if target not in expected[source]:
                        with self.assertRaises(ValueError): self.parse(article['articleBody'],article['headline'],target,{'home':home,'away':away},source)
                    else:
                        rows = self.parse(article['articleBody'],article['headline'],target,{'home':home,'away':away},source)['observations']
                        self.assertEqual(len(rows),expected[source][target])
                        if source == 'PIT' and target == 'ATL': self.assertEqual(rows[-1]['name'],'Ethan Onianwa')
                        if source == 'NO' and target == 'NO': self.assertEqual(rows[1]['status'],'EMERGENCY_QB')

    def test_explicit_opponent_headings_jerseys_and_english_positions(self):
        body = 'Some opening prose.Saints Inactives:\nNo. 11 Quarterback Zach Wilson (designated third QB)\nNo. 97 Defensive lineman Khristian BoydDetroit Lions inactives:\nNo. 2 Cornerback Ennis Rakestraw Jr.\nNo. 99 EDGE Ahmed Hassanein'
        game = {'home':'DET','away':'NO'}
        own = self.parse(body,'Saints Lions Inactives','NO',game)
        other = self.parse(body,'Saints Lions Inactives','DET',game,source_team='NO')
        self.assertEqual([r['name'] for r in own['observations']],['Zach Wilson','Khristian Boyd'])
        self.assertEqual(own['observations'][0]['status'],'EMERGENCY_QB')
        self.assertEqual([r['name'] for r in other['observations']],['Ennis Rakestraw Jr.','Ahmed Hassanein'])

    def test_ruled_out_intro_and_glued_footer(self):
        result = self.parse('The Jets ruled out two players ahead of the opener:\nLB One Player\nQB Two Player (3rd QB)\n\nOne Player was ruled out Saturday afternoon.','Jets Inactives')
        self.assertEqual(len(result['observations']),2)
        result = self.parse('Jets Inactives\nNo. 75 T Ethan OnianwaBringing you the action: For fans...','Jets Inactives')
        self.assertEqual(result['observations'][0]['name'],'Ethan Onianwa')

    def test_jaguars_explicit_list_uses_only_validated_dom_row_boundary(self):
        module=importlib.import_module('pgo_inactive_club')
        self.assertTrue(hasattr(module,'is_player_row'),'Public row validation is missing')
        for row in ['Offensive lineman Daniel Faalele','Defensive end Bryan Thomas Jr.','Safety Jalen Huskey']:
            self.assertTrue(module.is_player_row(row))
        self.assertFalse(module.is_player_row('Safety Jalen HuskeyAllen, who missed training camp, is active.'))
        self.assertFalse(module.is_player_row(None))
        item=next(r for r in json.loads((Path(__file__).parent/'fixtures/pgo_availability_v3_articles.json').read_text(encoding='utf-8')) if r['source_team']=='JAX')
        article=item['article'];body=article['articleBody']
        with self.assertRaises(ValueError): self.parse(body,article['headline'],'JAX',{'home':'JAX','away':'CLE'})
        for row in item['list_items']:
            self.assertTrue(module.is_player_row(row))
            body=body.replace(row,row+'\n',1)
        rows=self.parse(body,article['headline'],'JAX',{'home':'JAX','away':'CLE'})['observations']
        self.assertEqual([r['name'] for r in rows],['Quinn Ewers','Tanner Koziol','Daniel Faalele','Wesley Williams','Bryan Thomas Jr.','Jalen Huskey'])
        with self.assertRaises(ValueError): self.parse(body.replace('among six players','among seven players'),article['headline'],'JAX',{'home':'JAX','away':'CLE'})


if __name__ == '__main__':
    unittest.main()
